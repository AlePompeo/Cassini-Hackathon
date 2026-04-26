/**
 * packet.h — AquaGuard buoy 24-byte uplink packet codec
 *
 * Packet layout (24 bytes = 192 bits, fits Kinéis payload limit):
 *
 *  Byte  0:     buoy_id        uint8   unique buoy identifier (1–254)
 *  Bytes 1–4:   latitude_e5    int32   degrees × 1e5 (little-endian)
 *  Bytes 5–8:   longitude_e5   int32   degrees × 1e5 (little-endian)
 *  Byte  9:     gps_flags      uint8   bit0=fix_ok, bit1=galileo, bit2=egnos
 *  Bytes 10–11: bat_mv         uint16  battery voltage (mV, little-endian)
 *  Byte  12:    solar_pct      uint8   solar charge level (0–100 %)
 *  Byte  13:    temperature    int8    water temperature (°C, −128…+127)
 *  Byte  14:    oil_raw        uint8   oil film sensor (0=clean … 255=heavy)
 *  Byte  15:    uv_raw         uint8   UV fluorescence (0=none … 255=max)
 *  Byte  16:    turbidity      uint8   NTU / 10  (range 0–2550 NTU)
 *  Byte  17:    ph_x10         uint8   pH × 10   (range 0.0–14.0 pH)
 *  Byte  18:    do_x10         uint8   DO × 10 mg/L (range 0–25.5 mg/L)
 *  Byte  19:    alert_flags    uint8   see ALERT_* defines below
 *  Bytes 20–21: seq_num        uint16  rolling counter (little-endian)
 *  Bytes 22–23: crc16          uint16  CRC-16/CCITT-FALSE over bytes 0–21
 */

#pragma once
#include <stdint.h>

// alert_flags bit masks
#define ALERT_OIL        (1u << 0)   // oil film threshold exceeded
#define ALERT_UV         (1u << 1)   // UV fluorescence threshold exceeded
#define ALERT_ALGAE      (1u << 2)   // turbidity/pH suggests algal bloom
#define ALERT_LOW_BAT    (1u << 3)   // battery below BAT_LOW_MV
#define ALERT_GPS_FAIL   (1u << 4)   // no GPS fix within timeout
#define ALERT_SENSOR_ERR (1u << 5)   // one or more sensors returned invalid reading
#define ALERT_BACTERIA   (1u << 6)   // bacteria contamination risk (turbidity/pH/DO proxy)

// gps_flags bit masks
#define GPS_FIX_OK    (1u << 0)
#define GPS_GALILEO   (1u << 1)   // Galileo satellites used in solution
#define GPS_EGNOS     (1u << 2)   // EGNOS SBAS augmentation active

struct BuoyPacket {
    uint8_t   buoy_id;
    int32_t   latitude_e5;     // degrees × 100 000
    int32_t   longitude_e5;    // degrees × 100 000
    uint8_t   gps_flags;
    uint16_t  bat_mv;
    uint8_t   solar_pct;
    int8_t    temperature;
    uint8_t   oil_raw;
    uint8_t   uv_raw;
    uint8_t   turbidity;
    uint8_t   ph_x10;
    uint8_t   do_x10;
    uint8_t   alert_flags;
    uint16_t  seq_num;
};

/**
 * Encode a BuoyPacket into a 24-byte buffer.
 * Bytes 22–23 are set to the CRC-16/CCITT-FALSE of bytes 0–21.
 */
void packet_encode(const BuoyPacket* pkt, uint8_t buf[24]);

/**
 * Convert a 24-byte buffer to a null-terminated 48-char uppercase hex string.
 * `hex` must be at least 49 bytes.
 */
void packet_to_hex(const uint8_t buf[24], char hex[49]);

/**
 * CRC-16/CCITT-FALSE (polynomial 0x1021, init value 0xFFFF, no reflect).
 * Used both by the firmware and matched exactly by the Python decoder.
 */
uint16_t crc16_ccitt(const uint8_t* data, uint16_t len);
