/**
 * packet.cpp — AquaGuard buoy packet codec implementation
 */

#include "packet.h"
#include <string.h>

uint16_t crc16_ccitt(const uint8_t* data, uint16_t len) {
    uint16_t crc = 0xFFFFu;
    for (uint16_t i = 0; i < len; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (uint8_t b = 0; b < 8; b++) {
            crc = (crc & 0x8000u) ? (uint16_t)((crc << 1) ^ 0x1021u) : (uint16_t)(crc << 1);
        }
    }
    return crc;
}

void packet_encode(const BuoyPacket* p, uint8_t buf[24]) {
    memset(buf, 0, 24);

    buf[0] = p->buoy_id;

    // latitude_e5 — int32, little-endian
    buf[1] = (uint8_t)( p->latitude_e5        & 0xFF);
    buf[2] = (uint8_t)((p->latitude_e5 >>  8) & 0xFF);
    buf[3] = (uint8_t)((p->latitude_e5 >> 16) & 0xFF);
    buf[4] = (uint8_t)((p->latitude_e5 >> 24) & 0xFF);

    // longitude_e5 — int32, little-endian
    buf[5] = (uint8_t)( p->longitude_e5        & 0xFF);
    buf[6] = (uint8_t)((p->longitude_e5 >>  8) & 0xFF);
    buf[7] = (uint8_t)((p->longitude_e5 >> 16) & 0xFF);
    buf[8] = (uint8_t)((p->longitude_e5 >> 24) & 0xFF);

    buf[9]  = p->gps_flags;

    // bat_mv — uint16, little-endian
    buf[10] = (uint8_t)( p->bat_mv       & 0xFF);
    buf[11] = (uint8_t)((p->bat_mv >> 8) & 0xFF);

    buf[12] = p->solar_pct;
    buf[13] = (uint8_t)p->temperature;   // int8 reinterpret as uint8 is well-defined
    buf[14] = p->oil_raw;
    buf[15] = p->uv_raw;
    buf[16] = p->turbidity;
    buf[17] = p->ph_x10;
    buf[18] = p->do_x10;
    buf[19] = p->alert_flags;

    // seq_num — uint16, little-endian
    buf[20] = (uint8_t)( p->seq_num       & 0xFF);
    buf[21] = (uint8_t)((p->seq_num >> 8) & 0xFF);

    // CRC-16 over bytes 0–21, stored little-endian in bytes 22–23
    uint16_t crc = crc16_ccitt(buf, 22);
    buf[22] = (uint8_t)( crc       & 0xFF);
    buf[23] = (uint8_t)((crc >> 8) & 0xFF);
}

void packet_to_hex(const uint8_t buf[24], char hex[49]) {
    static const char lut[] = "0123456789ABCDEF";
    for (uint8_t i = 0; i < 24; i++) {
        hex[i * 2]     = lut[(buf[i] >> 4) & 0x0Fu];
        hex[i * 2 + 1] = lut[ buf[i]       & 0x0Fu];
    }
    hex[48] = '\0';
}
