/**
 * sensors.cpp — AquaGuard buoy sensor implementation
 */

#include "sensors.h"
#include "config.h"
#include <OneWire.h>
#include <DallasTemperature.h>

// ─── Static sensor instances ───────────────────────────────────
static OneWire         _ow(PIN_TEMP_ONEWIRE);
static DallasTemperature _temp_sensor(&_ow);
static TinyGPSPlus     _gps;

// GPS UART is Serial2 (ESP32)
#define GPS_SERIAL Serial2

// ─── SensorHub::begin ──────────────────────────────────────────
void SensorHub::begin() {
    // Analog pins — ESP32 ADC1
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);   // 0–3.3 V range

    // Power-enable outputs (modules start OFF)
    pinMode(PIN_KINEIS_PWREN, OUTPUT);
    pinMode(PIN_GPS_PWREN,    OUTPUT);
    pinMode(PIN_LED_STATUS,   OUTPUT);
    digitalWrite(PIN_KINEIS_PWREN, LOW);
    digitalWrite(PIN_GPS_PWREN,    LOW);
    digitalWrite(PIN_LED_STATUS,   LOW);

    // DS18B20
    _temp_sensor.begin();
    _temp_sensor.setResolution(12);   // 12-bit = 0.0625 °C resolution, ~750 ms

    // GPS UART
    GPS_SERIAL.begin(GPS_BAUD, SERIAL_8N1, GPS_UART_RX, GPS_UART_TX);
}

// ─── GPS ───────────────────────────────────────────────────────
GpsReading SensorHub::readGps() {
    GpsReading r = {};

    // Power on GPS module
    digitalWrite(PIN_GPS_PWREN, HIGH);
    delay(200);   // let module stabilise

    unsigned long deadline = millis() + (unsigned long)GPS_ACQUIRE_TIMEOUT_S * 1000UL;

    while (millis() < deadline) {
        while (GPS_SERIAL.available()) {
            _gps.encode(GPS_SERIAL.read());
        }
        if (_gps.location.isValid() && _gps.location.isUpdated()) {
            break;
        }
        delay(100);
    }

    digitalWrite(PIN_GPS_PWREN, LOW);   // power off GPS to save energy

    r.lat        = _gps.location.lat();
    r.lon        = _gps.location.lng();
    r.satellites = (uint8_t)_gps.satellites.value();
    r.fix_ok     = _gps.location.isValid();

    // u-blox NEO-M9N reports satellite system via $GNRMC / UBX-NAV-SAT.
    // TinyGPS++ does not expose constellation info directly; we infer from
    // the sentence talker ID seen on the serial stream.
    // For demo purposes we assume Galileo is used when fix is valid and
    // satellite count > 4 (conservative). Production firmware should parse
    // UBX binary protocol ($PUBX or UBX-NAV-SAT) for precise constellation info.
    r.galileo_used = r.fix_ok && (r.satellites > 4);
    r.egnos_active = false;   // set by GPGST / PUBX,03 SBAS flag in full impl

    return r;
}

// ─── Water quality ─────────────────────────────────────────────
WaterQuality SensorHub::readWater() {
    WaterQuality w = {};
    w.sensor_error = false;

    // DS18B20 temperature
    _temp_sensor.requestTemperatures();
    float temp = _temp_sensor.getTempCByIndex(0);
    if (temp == DEVICE_DISCONNECTED_C) {
        w.temperature_c = 20.0f;   // fallback
        w.sensor_error  = true;
    } else {
        w.temperature_c = temp;
    }

    // Oil film sensor — higher resistance when oil is present
    // Voltage increases with oil presence due to lower conductivity
    uint16_t oil_adc = analogRead(PIN_OIL_SENSOR);
    w.oil_raw = (uint8_t)(oil_adc * 255 / 4095);

    // UV fluorescence — aromatic hydrocarbons fluoresce under UV illumination
    // LED is always on; reading is ambient-subtracted in hardware
    uint16_t uv_adc = analogRead(PIN_UV_SENSOR);
    w.uv_raw = (uint8_t)(uv_adc * 255 / 4095);

    // Turbidity — inverted: lower voltage = higher turbidity (DF Robot sensor)
    uint16_t turb_adc = analogRead(PIN_TURBIDITY);
    // DF Robot SEN0189: output ≈ 4.5 V (clean) to 2.5 V (turbid) @ 5V supply
    // Scaled to 3.3 V rail: 2.97 V (clean) to ~1.65 V (turbid)
    // Map: high ADC = clean = low NTU
    float turb_ntu = _rawToTurbidityNtu(turb_adc);
    w.turbidity_raw = (uint8_t)constrain(turb_ntu / TURBIDITY_MAX_NTU * 255, 0, 255);

    // pH sensor — calibrated two-point
    uint16_t ph_adc = analogRead(PIN_PH);
    w.ph = _rawToPh(ph_adc);
    w.ph = constrain(w.ph, 0.0f, 14.0f);

    // Dissolved oxygen — membrane sensor, temperature compensated
    uint16_t do_adc = analogRead(PIN_DO);
    w.do_mgl = _rawToDo(do_adc);
    w.do_mgl = constrain(w.do_mgl, 0.0f, DO_MAX_MGL);

    // Bacteria contamination proxy (no dedicated sensor: derived from existing readings).
    // High turbidity, low DO, and extreme pH all correlate with bacterial risk.
    float turb_norm  = (float)w.turbidity_raw / 255.0f;
    float do_stress  = constrain(1.0f - w.do_mgl / 10.0f, 0.0f, 1.0f);
    float ph_dev     = (w.ph > 7.0f) ? (w.ph - 7.0f) / 4.0f : (7.0f - w.ph) / 4.0f;
    float bacteria_f = 0.5f * turb_norm + 0.3f * do_stress + 0.2f * constrain(ph_dev, 0.0f, 1.0f);
    w.bacteria_proxy = (uint8_t)constrain(bacteria_f * 255.0f, 0.0f, 255.0f);

    return w;
}

// ─── Power status ──────────────────────────────────────────────
PowerStatus SensorHub::readPower() {
    PowerStatus p = {};

    // Battery voltage via resistive divider: Vbat = Vadc × (R1+R2)/R2
    uint16_t bat_adc = analogRead(PIN_BATTERY_V);
    float vadc_mv    = (float)bat_adc / ADC_MAX_COUNTS * ADC_VREF_MV;
    float vbat_mv    = vadc_mv * (BAT_R1_KOHM + BAT_R2_KOHM) / BAT_R2_KOHM;
    p.bat_mv         = (uint16_t)constrain(vbat_mv, 0, 65535);

    // Solar current — simple ADC ratio (shunt amp output 0→3.3 V = 0→Imax)
    uint16_t sol_adc = analogRead(PIN_SOLAR_I);
    p.solar_pct      = (uint8_t)(sol_adc * 100 / 4095);

    p.low_battery      = p.bat_mv < BAT_LOW_MV;
    p.critical_battery = p.bat_mv < BAT_CRITICAL_MV;

    return p;
}

// ─── Private helpers ───────────────────────────────────────────
float SensorHub::_adcToVoltageMv(uint16_t raw) const {
    return (float)raw / ADC_MAX_COUNTS * ADC_VREF_MV;
}

float SensorHub::_rawToPh(uint16_t raw) const {
    // Two-point linear calibration
    // slope  = (7.0 - 4.0) / (PH_CAL_MV_PH7 - PH_CAL_MV_PH4)
    float mv     = _adcToVoltageMv(raw);
    float slope  = 3.0f / (PH_CAL_MV_PH7 - PH_CAL_MV_PH4);
    float ph     = 7.0f + slope * (mv - PH_CAL_MV_PH7);
    return ph;
}

float SensorHub::_rawToDo(uint16_t raw) const {
    // Linear mapping: 0 ADC → 0 mg/L, full-scale ADC → DO_MAX_MGL
    return (float)raw / ADC_MAX_COUNTS * DO_MAX_MGL;
}

float SensorHub::_rawToTurbidityNtu(uint16_t raw) const {
    // DF Robot SEN0189 characteristic (inverted): NTU ≈ (1 - raw/4095) * max_ntu
    float fraction = 1.0f - (float)raw / ADC_MAX_COUNTS;
    return fraction * TURBIDITY_MAX_NTU;
}
