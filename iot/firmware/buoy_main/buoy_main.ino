/**
 * buoy_main.ino — AquaGuard Smart Buoy firmware
 *
 * Operation cycle (repeats every TX_INTERVAL_NORMAL_MIN minutes):
 *   1. Wake from deep sleep (or power-on)
 *   2. Read all sensors (GPS, water quality, power)
 *   3. Build 24-byte packet and encode to hex
 *   4. Power on Kinéis KIM1, transmit packet, power off
 *   5. Log result to Serial (debug)
 *   6. Enter deep sleep until next interval
 *
 * Required Arduino libraries (install via Library Manager):
 *   - TinyGPS++ by Mikal Hart
 *   - OneWire by Paul Stoffregen
 *   - DallasTemperature by Miles Burton
 *
 * Board: ESP32 Dev Module (Tools → Board → ESP32 Arduino → ESP32 Dev Module)
 * Partition: Default (with OTA, 2 MB app / 2 MB SPIFFS)
 *
 * Kinéis KIM1 wiring:
 *   KIM TX  → ESP32 GPIO16 (KINEIS_UART_RX)
 *   KIM RX  → ESP32 GPIO17 (KINEIS_UART_TX)
 *   KIM VCC → 3.3 V via MOSFET controlled by GPIO5 (KINEIS_PWREN)
 *   KIM GND → GND
 *
 * GPS (u-blox NEO-M9N) wiring:
 *   GPS TX  → ESP32 GPIO26 (GPS_UART_RX)
 *   GPS RX  → ESP32 GPIO25 (GPS_UART_TX)
 *   GPS VCC → 3.3 V via MOSFET controlled by GPIO18 (GPS_PWREN)
 */

#include "config.h"
#include "packet.h"
#include "sensors.h"
#include "kineis.h"
#include "power.h"

// ─── Global objects ────────────────────────────────────────────
static SensorHub  sensors;
static KineisModem kineis(Serial1, PIN_KINEIS_PWREN);

// ─── setup ─────────────────────────────────────────────────────
void setup() {
    Serial.begin(SERIAL_DEBUG_BAUD);
    delay(100);   // allow USB-CDC to connect

    Serial.printf("\n[AquaGuard] Buoy #%d  FW %s  HW %s\n",
                  BUOY_ID, FW_VERSION, HW_REVISION);
    Serial.printf("[AquaGuard] Wake reason: %s\n", power_wake_reason());

    led_blink(2, 100);   // boot signal

    sensors.begin();

    // ── 1. Read power status first ─────────────────────────────
    PowerStatus pwr = sensors.readPower();
    Serial.printf("[POWER] bat=%u mV  solar=%u%%  low=%d  crit=%d\n",
                  pwr.bat_mv, pwr.solar_pct,
                  (int)pwr.low_battery, (int)pwr.critical_battery);

    if (pwr.critical_battery) {
        Serial.println("[POWER] Critical battery — emergency sleep 60 min.");
        led_blink(5, 50);
        power_deep_sleep(TX_INTERVAL_LOWBAT_MIN);
        return;   // unreachable; shown for clarity
    }

    // ── 2. Read GPS ────────────────────────────────────────────
    Serial.println("[GPS] Acquiring fix...");
    GpsReading gps = sensors.readGps();
    if (gps.fix_ok) {
        Serial.printf("[GPS] Fix OK: %.5f°N  %.5f°E  sats=%d  galileo=%d  egnos=%d\n",
                      gps.lat, gps.lon, gps.satellites,
                      (int)gps.galileo_used, (int)gps.egnos_active);
    } else {
        Serial.println("[GPS] No fix within timeout — using last known position.");
    }

    // ── 3. Read water quality sensors ─────────────────────────
    Serial.println("[SENSORS] Reading water quality...");
    WaterQuality wq = sensors.readWater();
    Serial.printf("[SENSORS] temp=%.1f C  oil=%u  uv=%u  turb=%u  pH=%.1f  DO=%.1f mg/L  bact=%u  err=%d\n",
                  wq.temperature_c, wq.oil_raw, wq.uv_raw, wq.turbidity_raw,
                  wq.ph, wq.do_mgl, wq.bacteria_proxy, (int)wq.sensor_error);

    // ── 4. Determine alert flags ───────────────────────────────
    uint8_t alerts = 0;
    if (wq.oil_raw   >= OIL_ALERT_THRESHOLD)     alerts |= ALERT_OIL;
    if (wq.uv_raw    >= UV_ALERT_THRESHOLD)       alerts |= ALERT_UV;
    if (wq.turbidity_raw >= ALGAE_TURBIDITY_THRESH &&
        (uint8_t)(wq.ph * 10.0f) > PH_LOW_ALERT) alerts |= ALERT_ALGAE;
    if (pwr.low_battery)                          alerts |= ALERT_LOW_BAT;
    if (!gps.fix_ok)                              alerts |= ALERT_GPS_FAIL;
    if (wq.sensor_error)                          alerts |= ALERT_SENSOR_ERR;
    if (wq.bacteria_proxy >= BACTERIA_ALERT_THRESHOLD) alerts |= ALERT_BACTERIA;

    if (alerts) {
        Serial.printf("[ALERT] flags=0x%02X\n", alerts);
        led_blink(3, 80);
    }

    // ── 5. Build packet ────────────────────────────────────────
    BuoyPacket pkt = {};
    pkt.buoy_id      = BUOY_ID;
    pkt.latitude_e5  = (int32_t)(gps.lat  * 1e5);
    pkt.longitude_e5 = (int32_t)(gps.lon  * 1e5);
    pkt.gps_flags    = (gps.fix_ok      ? GPS_FIX_OK  : 0u)
                     | (gps.galileo_used ? GPS_GALILEO : 0u)
                     | (gps.egnos_active ? GPS_EGNOS   : 0u);
    pkt.bat_mv       = pwr.bat_mv;
    pkt.solar_pct    = pwr.solar_pct;
    pkt.temperature  = (int8_t)constrain((int)wq.temperature_c, -128, 127);
    pkt.oil_raw      = wq.oil_raw;
    pkt.uv_raw       = wq.uv_raw;
    pkt.turbidity    = wq.turbidity_raw;
    pkt.ph_x10       = (uint8_t)constrain((int)(wq.ph * 10), 0, 140);
    pkt.do_x10       = (uint8_t)constrain((int)(wq.do_mgl * 10), 0, 255);
    pkt.alert_flags  = alerts;
    pkt.seq_num      = power_next_seq();

    uint8_t buf[24];
    char    hex[49];
    packet_encode(&pkt, buf);
    packet_to_hex(buf, hex);
    Serial.printf("[PACKET] seq=%u  hex=%s\n", pkt.seq_num, hex);

    // ── 6. Transmit via Kinéis ─────────────────────────────────
    Serial.println("[KINEIS] Powering on KIM module...");
    if (kineis.begin()) {
        char device_id[16];
        if (kineis.getDeviceId(device_id)) {
            Serial.printf("[KINEIS] Device ID: %s\n", device_id);
        }

        Serial.println("[KINEIS] Transmitting...");
        KineisResult result = kineis.send(hex, KINEIS_TX_TIMEOUT_MS);

        switch (result) {
            case KineisResult::OK:
                Serial.println("[KINEIS] TX scheduled OK.");
                led_blink(1, 300);
                break;
            case KineisResult::ERR_TIMEOUT:
                Serial.println("[KINEIS] TX timeout — will retry next cycle.");
                led_blink(4, 100);
                break;
            case KineisResult::ERR_NACK:
                Serial.println("[KINEIS] TX NACK — module error.");
                led_blink(6, 50);
                break;
            default:
                Serial.println("[KINEIS] TX unknown error.");
                break;
        }

        kineis.powerOff();
    } else {
        Serial.println("[KINEIS] Module not responding — skipping TX.");
        led_blink(8, 50);
    }

    // ── 7. Determine next sleep interval ─────────────────────
    uint32_t sleep_min = (alerts & (ALERT_OIL | ALERT_UV | ALERT_BACTERIA))
                         ? TX_INTERVAL_ALERT_MIN
                         : pwr.low_battery
                           ? TX_INTERVAL_LOWBAT_MIN
                           : TX_INTERVAL_NORMAL_MIN;

    Serial.printf("[POWER] Entering deep sleep for %u min.\n\n", sleep_min);
    Serial.flush();

    power_deep_sleep(sleep_min);
}

// loop() is never reached because setup() ends with deep sleep
void loop() {}

