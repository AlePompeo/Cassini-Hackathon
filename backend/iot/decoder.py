"""Binary packet decoder for AquaGuard buoy 24-byte uplink packets.

This module mirrors the firmware's packet.h/packet.cpp layout exactly.
Any change to the packet format in the firmware must be reflected here.

Packet layout (24 bytes, all little-endian):
  [0]     buoy_id        uint8
  [1:5]   latitude_e5    int32   (degrees × 1e5)
  [5:9]   longitude_e5   int32   (degrees × 1e5)
  [9]     gps_flags      uint8   (bit0=fix_ok, bit1=galileo, bit2=egnos)
  [10:12] bat_mv         uint16  (mV)
  [12]    solar_pct      uint8   (0–100 %)
  [13]    temperature    int8    (°C)
  [14]    oil_raw        uint8
  [15]    uv_raw         uint8
  [16]    turbidity      uint8   (NTU/10)
  [17]    ph_x10         uint8   (pH × 10)
  [18]    do_x10         uint8   (DO × 10 mg/L)
  [19]    alert_flags    uint8
  [20:22] seq_num        uint16
  [22:24] crc16          uint16  (CRC-16/CCITT-FALSE of bytes 0–21)
"""

from __future__ import annotations

import struct
from typing import Final

from exceptions import AquaGuardError
from models.buoy import (
    AlertFlag,
    BuoyTelemetry,
    GpsInfo,
    PowerReadings,
    WaterReadings,
    decode_alert_flags,
)

PACKET_SIZE: Final[int] = 24

# GPS flag bits
_GPS_FIX_OK: Final[int]  = 1 << 0
_GPS_GALILEO: Final[int] = 1 << 1
_GPS_EGNOS: Final[int]   = 1 << 2

# Water quality scale factors (must match firmware)
_TURBIDITY_MAX_NTU: Final[float] = 2550.0
_DO_MAX_MGL: Final[float]        = 25.5


class PacketDecodeError(AquaGuardError):
    """Raised when a buoy packet cannot be decoded (bad length, CRC, etc.)."""


def _crc16_ccitt(data: bytes) -> int:
    """CRC-16/CCITT-FALSE: poly=0x1021, init=0xFFFF, no reflect."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def decode_packet(
    hex_payload: str,
    kineis_device_id: str = "",
    satellite_id: str = "",
) -> BuoyTelemetry:
    """Decode a 48-hex-char (24-byte) buoy uplink packet.

    Args:
        hex_payload: Uppercase or lowercase 48-character hex string.
        kineis_device_id: Kinéis device identifier from the webhook metadata.
        satellite_id: Kinéis satellite that received the uplink.

    Returns:
        Fully decoded BuoyTelemetry instance.

    Raises:
        PacketDecodeError: If the payload length, hex encoding, or CRC is wrong.
    """
    hex_clean = hex_payload.strip().upper()
    if len(hex_clean) != 48:
        raise PacketDecodeError(
            f"Expected 48 hex chars (24 bytes), got {len(hex_clean)}."
        )

    try:
        raw = bytes.fromhex(hex_clean)
    except ValueError as exc:
        raise PacketDecodeError(f"Invalid hex payload: {exc}") from exc

    # CRC verification
    received_crc = struct.unpack_from("<H", raw, 22)[0]
    computed_crc = _crc16_ccitt(raw[:22])
    if received_crc != computed_crc:
        raise PacketDecodeError(
            f"CRC mismatch: received 0x{received_crc:04X}, "
            f"computed 0x{computed_crc:04X}."
        )

    # Unpack fields
    (buoy_id,) = struct.unpack_from("B", raw, 0)
    (lat_e5,)  = struct.unpack_from("<i", raw, 1)
    (lon_e5,)  = struct.unpack_from("<i", raw, 5)
    (gps_flags,) = struct.unpack_from("B", raw, 9)
    (bat_mv,)    = struct.unpack_from("<H", raw, 10)
    (solar_pct,) = struct.unpack_from("B", raw, 12)
    (temp_raw,)  = struct.unpack_from("b", raw, 13)    # signed int8
    (oil_raw,)   = struct.unpack_from("B", raw, 14)
    (uv_raw,)    = struct.unpack_from("B", raw, 15)
    (turb_raw,)  = struct.unpack_from("B", raw, 16)
    (ph_x10,)    = struct.unpack_from("B", raw, 17)
    (do_x10,)    = struct.unpack_from("B", raw, 18)
    (alert_raw,) = struct.unpack_from("B", raw, 19)
    (seq_num,)   = struct.unpack_from("<H", raw, 20)

    # Scale raw values to physical units
    latitude  = lat_e5 / 1e5
    longitude = lon_e5 / 1e5
    ph        = ph_x10 / 10.0
    do_mgl    = do_x10 / 10.0
    turb_ntu  = turb_raw * (_TURBIDITY_MAX_NTU / 255.0)

    # Bacteria contamination risk index [0, 1] — mirrors firmware proxy formula
    _turb_f      = min(1.0, turb_ntu / 500.0) * 0.5
    _do_f        = max(0.0, 1.0 - do_mgl / 10.0) * 0.3
    _ph_f        = min(1.0, abs(ph - 7.0) / 4.0) * 0.2
    bacteria_est = round(min(1.0, _turb_f + _do_f + _ph_f), 3)

    gps = GpsInfo(
        fix_ok       = bool(gps_flags & _GPS_FIX_OK),
        galileo_used = bool(gps_flags & _GPS_GALILEO),
        egnos_active = bool(gps_flags & _GPS_EGNOS),
    )

    water = WaterReadings(
        temperature_c = float(temp_raw),
        oil_raw       = oil_raw,
        uv_raw        = uv_raw,
        turbidity_ntu = round(turb_ntu, 1),
        ph            = round(ph, 1),
        do_mgl        = round(do_mgl, 1),
        bacteria_est  = bacteria_est,
        sensor_error  = bool(alert_raw & (1 << 5)),
    )

    power = PowerReadings(
        bat_mv      = bat_mv,
        solar_pct   = solar_pct,
        low_battery = bool(alert_raw & (1 << 3)),
    )

    alerts = decode_alert_flags(alert_raw)

    return BuoyTelemetry(
        buoy_id          = buoy_id,
        seq_num          = seq_num,
        latitude         = latitude,
        longitude        = longitude,
        gps              = gps,
        water            = water,
        power            = power,
        alerts           = alerts,
        raw_hex          = hex_clean,
        kineis_device_id = kineis_device_id,
        satellite_id     = satellite_id,
    )
