/**
 * kineis.cpp — Kinéis KIM1 AT command driver implementation
 */

#include "kineis.h"
#include "config.h"
#include <string.h>
#include <stdio.h>

KineisModem::KineisModem(HardwareSerial& uart, uint8_t pwren_pin)
    : _uart(uart), _pwren(pwren_pin) {}

bool KineisModem::begin() {
    pinMode(_pwren, OUTPUT);
    digitalWrite(_pwren, HIGH);
    delay(1500);   // KIM1 boot time

    _uart.begin(KINEIS_BAUD, SERIAL_8N1, KINEIS_UART_RX, KINEIS_UART_TX);
    delay(200);
    _flush();

    // Verify module responds to AT echo
    for (uint8_t attempt = 0; attempt < 5; attempt++) {
        if (_sendCmd("AT", "OK", 1000)) return true;
        delay(500);
    }
    return false;
}

KineisResult KineisModem::send(const char* hex_payload, uint32_t timeout_ms) {
    if (!hex_payload) return KineisResult::ERR_PAYLOAD_TOO_LONG;

    uint16_t len = (uint16_t)strlen(hex_payload);
    if (len > 48) return KineisResult::ERR_PAYLOAD_TOO_LONG;   // > 24 bytes

    // Build command: AT+SEND=<hex>\r\n
    char cmd[64];
    snprintf(cmd, sizeof(cmd), "AT+SEND=%s", hex_payload);

    _flush();
    _uart.print(cmd);
    _uart.print("\r\n");

    // Wait for OK or ERR within timeout
    char resp[32];
    uint32_t deadline = millis() + timeout_ms;
    while (millis() < deadline) {
        if (_readLine(resp, sizeof(resp), 500)) {
            if (strncmp(resp, "OK", 2) == 0)  return KineisResult::OK;
            if (strncmp(resp, "ERR", 3) == 0) return KineisResult::ERR_NACK;
        }
    }
    return KineisResult::ERR_TIMEOUT;
}

bool KineisModem::getDeviceId(char out_id[16]) {
    _flush();
    _uart.print("AT+ID?\r\n");

    char line[32];
    if (!_readLine(line, sizeof(line), 2000)) return false;

    // Response format: "+ID: XXXXXXXXXXXX" then "OK"
    const char* prefix = "+ID: ";
    char* id_start = strstr(line, prefix);
    if (!id_start) return false;

    strncpy(out_id, id_start + strlen(prefix), 15);
    out_id[15] = '\0';
    return true;
}

void KineisModem::sleep() {
    _sendCmd("AT+SLEEP", "OK", 1000);
}

void KineisModem::powerOff() {
    sleep();
    delay(100);
    digitalWrite(_pwren, LOW);
}

// ─── Private helpers ───────────────────────────────────────────

bool KineisModem::_sendCmd(const char* cmd, const char* expect, uint32_t timeout_ms) {
    _flush();
    _uart.print(cmd);
    _uart.print("\r\n");

    char line[64];
    uint32_t deadline = millis() + timeout_ms;
    while (millis() < deadline) {
        if (_readLine(line, sizeof(line), 300)) {
            if (strstr(line, expect) != nullptr) return true;
        }
    }
    return false;
}

bool KineisModem::_readLine(char* buf, uint16_t len, uint32_t timeout_ms) {
    uint16_t pos = 0;
    uint32_t deadline = millis() + timeout_ms;

    while (millis() < deadline) {
        if (_uart.available()) {
            char c = (char)_uart.read();
            if (c == '\n') {
                // Strip trailing \r if present
                if (pos > 0 && buf[pos - 1] == '\r') pos--;
                buf[pos] = '\0';
                return pos > 0;
            }
            if (pos < len - 1) buf[pos++] = c;
        }
    }
    buf[pos] = '\0';
    return false;
}

void KineisModem::_flush() {
    while (_uart.available()) _uart.read();
}
