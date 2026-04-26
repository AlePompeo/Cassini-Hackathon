/**
 * config.h — AquaGuard Smart Buoy configuration
 *
 * Target MCU: ESP32 DevKit v1 (Xtensa LX6 dual-core, 240 MHz)
 * Tested board: ESP32-WROOM-32
 *
 * External libraries required (install via Arduino Library Manager):
 *   - TinyGPS++ by Mikal Hart (GPS NMEA parsing)
 *   - OneWire by Paul Stoffregen
 *   - DallasTemperature by Miles Burton (DS18B20 driver)
 */

#pragma once

// ─── Firmware identity ─────────────────────────────────────────
#define FW_VERSION   "1.0.0"
#define HW_REVISION  "1.0"

// ─── Buoy identity (change per physical unit) ──────────────────
// Range 1–254. 0 and 255 are reserved.
#define BUOY_ID      1

// ─── UART pin assignments ───────────────────────────────────────
// Serial0 (USB) — debug console
#define SERIAL_DEBUG_BAUD   115200

// Serial1 — Kinéis KIM module (AT commands)
#define KINEIS_UART_TX      17
#define KINEIS_UART_RX      16
#define KINEIS_BAUD         9600

// Serial2 — GPS (NMEA 0183)
#define GPS_UART_TX         25
#define GPS_UART_RX         26
#define GPS_BAUD            9600

// ─── Analog sensor pins (ADC1 — safe to use during Wi-Fi; unused here) ──
#define PIN_OIL_SENSOR      34    // Oil film resistive sensor (ADC1_CH6)
#define PIN_UV_SENSOR       35    // UV fluorescence photodiode (ADC1_CH7)
#define PIN_TURBIDITY       32    // Optical turbidity sensor   (ADC1_CH4)
#define PIN_PH              33    // Analog pH electrode        (ADC1_CH5)
#define PIN_DO              36    // Dissolved oxygen analog    (ADC1_CH0 / VP)
#define PIN_BATTERY_V       39    // Battery voltage divider    (ADC1_CH3 / VN)
#define PIN_SOLAR_I         38    // Solar current shunt        (ADC1_CH2)

// ─── Digital pins ───────────────────────────────────────────────
#define PIN_TEMP_ONEWIRE    4     // DS18B20 1-Wire data line
#define PIN_KINEIS_PWREN    5     // HIGH → Kinéis module power on
#define PIN_GPS_PWREN       18    // HIGH → GPS module power on
#define PIN_LED_STATUS      2     // Onboard LED (active HIGH)

// ─── ADC / voltage scaling ──────────────────────────────────────
// Battery voltage divider: R1 = 100 kΩ, R2 = 47 kΩ
//   Vbat = Vadc × (R1 + R2) / R2
#define BAT_R1_KOHM         100.0f
#define BAT_R2_KOHM          47.0f
#define ADC_VREF_MV        3300.0f   // ESP32 ADC reference
#define ADC_MAX_COUNTS     4095.0f   // 12-bit ADC

// ─── pH calibration (two-point: adjust after field calibration) ─
// Slope: mV drop per pH unit (typical −59.2 mV/pH at 25 °C)
#define PH_CAL_MV_PH4     1745.0f   // measured output at pH 4.0 buffer
#define PH_CAL_MV_PH7     1565.0f   // measured output at pH 7.0 buffer

// ─── Sensor scale factors ───────────────────────────────────────
#define TURBIDITY_MAX_NTU  2550.0f  // Full-scale turbidity
#define DO_MAX_MGL           25.5f  // Full-scale dissolved oxygen (mg/L)

// ─── Alert thresholds ───────────────────────────────────────────
#define OIL_ALERT_THRESHOLD     70    // Oil raw value 0–255 (above → oil alert)
#define UV_ALERT_THRESHOLD     110    // UV raw 0–255 (above → UV hydrocarbon alert)
#define ALGAE_TURBIDITY_THRESH 200    // Turbidity raw 0–255 (proxy for bloom)
#define PH_LOW_ALERT            60    // pH × 10 = 6.0 (below → acidity alert)
#define PH_HIGH_ALERT           90    // pH × 10 = 9.0 (above → alkalinity alert)

// Bacteria proxy alert: software-estimated from turbidity + pH deviation + low DO
// Proxy = 0.5*(turb/255) + 0.3*(1-DO/10) + 0.2*(|pH-7|/4), scaled 0-255
#define BACTERIA_ALERT_THRESHOLD  80  // proxy raw 0-255 (above -> bacteria contamination alert)

// ─── Power management ───────────────────────────────────────────
#define BAT_LOW_MV          3500    // mV — set low-battery flag
#define BAT_CRITICAL_MV     3200    // mV — enter emergency deep sleep (4 h)

// Solar current shunt: 0.1 Ω shunt resistor, INA219 or direct ADC
// Solar_I_mA = (Vadc_solar - Vadc_ground) / 0.0001 (simplified)
// For demo: solar_pct = min(100, solar_adc_raw * 100 / 4095)

// ─── Transmission schedule ──────────────────────────────────────
#define TX_INTERVAL_NORMAL_MIN    15    // Normal telemetry interval (minutes)
#define TX_INTERVAL_ALERT_MIN      2    // Alert mode interval (minutes)
#define TX_INTERVAL_LOWBAT_MIN    60    // Low-battery interval (minutes)
#define GPS_ACQUIRE_TIMEOUT_S     90    // Seconds to wait for GPS fix before giving up
#define KINEIS_TX_TIMEOUT_MS   30000    // ms to wait for KIM TX acknowledgement

// ─── Packet ─────────────────────────────────────────────────────
#define PACKET_SIZE_BYTES         24    // Fits within Kinéis 192-bit payload limit
