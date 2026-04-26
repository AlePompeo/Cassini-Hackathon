/**
 * kineis.h — Kinéis KIM1 module AT command driver
 *
 * The Kinéis KIM1 (Kinéis Integrated Module) transmits data to the
 * Kinéis LEO satellite constellation via VHF uplink (401.65 MHz).
 * Communication with the host MCU is via UART AT commands.
 *
 * Key module specs:
 *   - Payload: up to 192 bits (24 bytes) per message
 *   - TX power: ~100 mW (adjustable)
 *   - Frequency: 401.65 MHz (Argos-4 / Kinéis band)
 *   - Sleep current: ~5 µA
 *
 * AT command reference (KIM1 firmware ≥ 2.0):
 *   AT                       — echo test (responds OK)
 *   AT+ID?                   — get device ID (hex string)
 *   AT+FW?                   — get firmware version
 *   AT+SEND=<hex>            — transmit hex payload (max 48 hex chars = 24 bytes)
 *   AT+STATUS?               — get module status
 *   AT+SLEEP                 — put KIM into low-power mode
 *   AT+WAKE                  — wake from sleep
 */

#pragma once
#include <Arduino.h>

enum class KineisResult : uint8_t {
    OK,
    ERR_TIMEOUT,
    ERR_NACK,
    ERR_PAYLOAD_TOO_LONG,
    ERR_NOT_READY,
};

class KineisModem {
public:
    /**
     * Attach to the UART stream used for KIM communication.
     * Call before begin().
     *
     * @param uart  HardwareSerial port connected to KIM (e.g., Serial1)
     * @param pwren Pin number for modem power enable (HIGH = on)
     */
    KineisModem(HardwareSerial& uart, uint8_t pwren_pin);

    /**
     * Power on the KIM module and verify it responds to AT.
     * Returns true if module is ready within 3 s.
     */
    bool begin();

    /**
     * Transmit a 48-char hex string (24 bytes) via the Kinéis network.
     *
     * Blocks until the module confirms the transmission has been scheduled
     * (not necessarily received by a satellite — LEO pass timing is managed
     * autonomously by the KIM module).
     *
     * @param hex_payload  48-character uppercase hex string (null-terminated)
     * @param timeout_ms   Maximum time to wait for OK/ERR response
     */
    KineisResult send(const char* hex_payload, uint32_t timeout_ms = 30000);

    /**
     * Read the module's unique device ID.
     * @param out_id  Buffer of at least 16 bytes.
     * Returns true on success.
     */
    bool getDeviceId(char out_id[16]);

    /**
     * Put the KIM module into its low-power sleep state.
     * Wake is automatic on transmission schedule or via AT+WAKE.
     */
    void sleep();

    /** Power off the KIM module entirely (cuts PWREN). */
    void powerOff();

private:
    HardwareSerial& _uart;
    uint8_t         _pwren;

    /** Send an AT command and wait for a response line. */
    bool _sendCmd(const char* cmd, const char* expect, uint32_t timeout_ms = 3000);

    /** Read a response line (terminated by \r\n) into buf (max len bytes). */
    bool _readLine(char* buf, uint16_t len, uint32_t timeout_ms = 3000);

    /** Flush all pending UART input. */
    void _flush();
};
