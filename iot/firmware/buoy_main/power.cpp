/**
 * power.cpp — ESP32 power management implementation
 */

#include "power.h"
#include "config.h"

// Persists across deep sleep restarts; lost on full power cycle
RTC_DATA_ATTR uint16_t g_seq_num = 0;

void power_deep_sleep(uint32_t minutes) {
    uint64_t us = (uint64_t)minutes * 60ULL * 1000000ULL;
    esp_sleep_enable_timer_wakeup(us);
    Serial.flush();
    esp_deep_sleep_start();
    // Execution never reaches here; resumes at setup() after wake
}

uint16_t power_next_seq() {
    return ++g_seq_num;   // wraps naturally at uint16_t overflow
}

void led_blink(uint8_t n, uint16_t period_ms) {
    for (uint8_t i = 0; i < n; i++) {
        digitalWrite(PIN_LED_STATUS, HIGH);
        delay(period_ms);
        digitalWrite(PIN_LED_STATUS, LOW);
        delay(period_ms);
    }
}

const char* power_wake_reason() {
    esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();
    switch (cause) {
        case ESP_SLEEP_WAKEUP_TIMER:    return "timer";
        case ESP_SLEEP_WAKEUP_EXT0:     return "ext0";
        case ESP_SLEEP_WAKEUP_EXT1:     return "ext1";
        case ESP_SLEEP_WAKEUP_TOUCHPAD: return "touchpad";
        default:                        return "power-on";
    }
}
