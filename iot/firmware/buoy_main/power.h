/**
 * power.h — AquaGuard buoy power management (ESP32 deep sleep)
 *
 * Between telemetry transmissions the ESP32 enters deep sleep:
 *   - Current draw: ~10 µA (vs ~80 mA active)
 *   - Wake source: RTC timer (configurable interval)
 *   - RTC memory persists across deep sleep (not power cycles)
 *
 * The sequence number is stored in RTC memory so it survives sleep
 * restarts without requiring EEPROM writes.
 */

#pragma once
#include <Arduino.h>
#include <esp_sleep.h>

// Sequence number persists across deep sleep via RTC memory.
// Declared extern here; defined (with RTC_DATA_ATTR) in power.cpp.
extern uint16_t g_seq_num;

/**
 * Enter ESP32 deep sleep for `minutes` minutes.
 * All peripherals must be powered off before calling.
 * Execution resumes from setup() on wake.
 */
void power_deep_sleep(uint32_t minutes);

/**
 * Increment and return the rolling sequence number.
 * Wraps at 65535 → 0.
 */
uint16_t power_next_seq();

/**
 * Blink the status LED n times with `period_ms` half-period.
 * Used to signal boot, TX success, or error codes.
 */
void led_blink(uint8_t n, uint16_t period_ms = 200);

/**
 * Return the wake-up cause as a human-readable string.
 * Useful for debug logging on startup.
 */
const char* power_wake_reason();
