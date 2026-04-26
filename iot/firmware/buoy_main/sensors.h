/**
 * sensors.h — AquaGuard buoy sensor abstraction layer
 *
 * Wraps all physical sensors into a single SensorHub class.
 * Call SensorHub::begin() in setup(), then SensorHub::read() each cycle.
 *
 * Sensor hardware:
 *   - Oil film:     Resistive conductive sensor (analog, ADC)
 *   - UV fluorescence: UV-LED + TAOS TSL257 photodiode (analog, ADC)
 *   - Turbidity:    DF Robot SEN0189 optical turbidity (analog, ADC)
 *   - pH:           Analog pH electrode + signal conditioning board (ADC)
 *   - DO:           Analog dissolved oxygen membrane sensor (ADC)
 *   - Temperature:  Dallas DS18B20 (1-Wire digital)
 *   - GPS:          u-blox NEO-M9N (UART NMEA, Galileo-capable)
 *   - Battery:      Voltage divider on ADC
 *   - Solar:        Current shunt on ADC
 */

#pragma once
#include <Arduino.h>
#include <TinyGPS++.h>

struct GpsReading {
    double   lat;
    double   lon;
    uint8_t  satellites;
    bool     fix_ok;
    bool     galileo_used;   // u-blox UBX-NAV-SAT Galileo constellation active
    bool     egnos_active;   // SBAS/EGNOS DGPS augmentation active
};

struct WaterQuality {
    float    temperature_c;     // °C  (−20 … +60)
    uint8_t  oil_raw;           // 0–255  (0 = no oil)
    uint8_t  uv_raw;            // 0–255  (0 = no fluorescence)
    uint8_t  turbidity_raw;     // 0–255  (0 = crystal clear)
    float    ph;                // 0.0–14.0
    float    do_mgl;            // 0.0–25.5 mg/L
    uint8_t  bacteria_proxy;    // 0–255 contamination risk estimate (turbidity+pH+DO proxy)
    bool     sensor_error;      // true if any reading failed
};

struct PowerStatus {
    uint16_t bat_mv;            // battery voltage (mV)
    uint8_t  solar_pct;         // solar charge current as % of max (0–100)
    bool     low_battery;       // bat_mv < BAT_LOW_MV
    bool     critical_battery;  // bat_mv < BAT_CRITICAL_MV
};

class SensorHub {
public:
    /**
     * Initialise all sensor buses and pins.
     * Call once from Arduino setup().
     */
    void begin();

    /**
     * Power on GPS, acquire fix (up to GPS_ACQUIRE_TIMEOUT_S), then power off.
     * Fills reading with last known position on timeout.
     */
    GpsReading readGps();

    /**
     * Read all water quality sensors.
     * DS18B20 conversion takes ~750 ms (blocking).
     */
    WaterQuality readWater();

    /**
     * Read battery voltage and solar current.
     * Fast ADC reads — call any time.
     */
    PowerStatus readPower();

private:
    float  _adcToVoltage(uint16_t raw) const;
    float  _adcToVoltageMv(uint16_t raw) const;
    float  _rawToPh(uint16_t raw) const;
    float  _rawToDo(uint16_t raw) const;
    float  _rawToTurbidityNtu(uint16_t raw) const;
};
