"""AquaGuard buoy simulator.

Generates synthetic buoy telemetry packets that match the 24-byte firmware
format exactly and POSTs them to the AquaGuard backend webhook endpoint.

Usage:
    python buoy_simulator.py --buoys 3 --interval 15 --endpoint http://localhost:8000

Options:
    --buoys     N     number of simulated buoys (default: 3)
    --interval  MIN   transmission interval in minutes (default: 15)
    --endpoint  URL   backend base URL (default: http://localhost:8000)
    --once            send one batch of readings and exit
    --oil-event       inject an oil spill event on buoy 1 for one reading

The simulator mirrors the firmware CRC algorithm, packet layout, and sensor
value encoding so that the backend decoder processes simulated packets exactly
as it would real hardware uplinks.
"""

from __future__ import annotations

import argparse
import math
import random
import struct
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime

try:
    import httpx
except ImportError:
    sys.exit("httpx is required: pip install httpx")


# ─── CRC-16/CCITT-FALSE (must match firmware) ──────────────────────────────
def _crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


# ─── Packet encoder (mirrors firmware packet.cpp) ──────────────────────────
def encode_packet(
    buoy_id:      int,
    lat:          float,
    lon:          float,
    gps_flags:    int,
    bat_mv:       int,
    solar_pct:    int,
    temperature:  int,
    oil_raw:      int,
    uv_raw:       int,
    turbidity:    int,
    ph_x10:       int,
    do_x10:       int,
    alert_flags:  int,
    seq_num:      int,
) -> bytes:
    """Pack fields into a 24-byte buffer with appended CRC-16."""
    lat_e5 = int(lat * 1e5)
    lon_e5 = int(lon * 1e5)

    buf = struct.pack(
        "<BiiB HBb BBBBB BB H",
        buoy_id,
        lat_e5,
        lon_e5,
        gps_flags,
        bat_mv,
        solar_pct,
        temperature,    # signed int8
        oil_raw,
        uv_raw,
        turbidity,
        ph_x10,
        do_x10,
        alert_flags,
        0,              # seq_num placeholder (low byte only so far)
        seq_num,        # this covers both seq bytes via uint16
    )
    # The struct above is 22 bytes; append CRC-16
    # Actually re-pack more carefully:
    buf22 = bytearray(22)
    buf22[0]  = buoy_id & 0xFF
    struct.pack_into("<i", buf22, 1,  lat_e5)
    struct.pack_into("<i", buf22, 5,  lon_e5)
    buf22[9]  = gps_flags & 0xFF
    struct.pack_into("<H", buf22, 10, bat_mv)
    buf22[12] = solar_pct & 0xFF
    buf22[13] = temperature & 0xFF    # int8 → uint8 reinterpret
    buf22[14] = oil_raw & 0xFF
    buf22[15] = uv_raw & 0xFF
    buf22[16] = turbidity & 0xFF
    buf22[17] = ph_x10 & 0xFF
    buf22[18] = do_x10 & 0xFF
    buf22[19] = alert_flags & 0xFF
    struct.pack_into("<H", buf22, 20, seq_num)

    crc = _crc16_ccitt(bytes(buf22))
    return bytes(buf22) + struct.pack("<H", crc)


# ─── Simulated buoy state ──────────────────────────────────────────────────
@dataclass
class SimBuoy:
    """Tracks the state of a single simulated buoy across transmissions."""

    buoy_id:   int
    lat:       float   # current position
    lon:       float
    seq_num:   int = 0
    bat_mv:    int = 4100     # LiPo starting at ~4.1 V
    solar_pct: int = 65
    oil_event:      bool = False   # true → inject elevated oil/UV readings
    bacteria_event: bool = False   # true → inject high turbidity / low DO

    # Deployment positions — coastal, lakes, rivers, dams, aqueducts (lon, lat)
    _SEEDS: list[tuple[float, float]] = field(default_factory=lambda: [
        (12.57, 44.06),   # Rimini Beach (Adriatic coast)
        (14.48, 40.63),   # Positano, Amalfi Coast
        (7.27,  43.70),   # Nice, Cote d'Azur
        (18.09, 42.65),   # Dubrovnik, Croatia
        (3.07,  39.57),   # Alcudia, Mallorca
        (17.89, 40.25),   # Porto Cesareo (marine reserve)
        (10.72, 45.63),   # Lake Garda
        (9.26,  46.00),   # Lake Como
        (12.10, 43.12),   # Lake Trasimeno
        (12.47, 41.89),   # Tiber River, Rome
        (12.25, 44.55),   # Po River Delta
        (11.25, 43.77),   # Arno, Florence
        (4.83,  43.93),   # Rhone, Avignon
        (16.02, 40.28),   # Lago del Pertusillo (dam)
        (11.98, 43.94),   # Lago di Bilancino (reservoir)
        (12.34, 46.27),   # Lago del Vajont (historic dam site)
        (12.54, 41.86),   # Aqua Claudia, Rome (aqueduct)
        (4.54,  43.94),   # Pont du Gard, France
        (-4.12, 40.95),   # Segovia Aqueduct, Spain
        (12.45, 37.50),   # Strait of Sicily (original maritime zone)
    ])

    @classmethod
    def create(cls, buoy_id: int, oil_event: bool = False) -> "SimBuoy":
        seeds = cls._SEEDS.fget(None)  # type: ignore[attr-defined]
        lon, lat = seeds[(buoy_id - 1) % len(seeds)]
        return cls(buoy_id=buoy_id, lat=lat, lon=lon, oil_event=oil_event)

    def drift(self) -> None:
        """Simulate slow buoy drift due to wind and current."""
        self.lat += random.gauss(0.001, 0.003)
        self.lon += random.gauss(0.002, 0.003)

    def discharge(self) -> None:
        """Battery discharges slowly; solar recharges during day."""
        hour = datetime.utcnow().hour
        is_day = 6 <= hour <= 20
        solar_input = random.randint(20, 80) if is_day else 0
        self.solar_pct = min(100, solar_input)
        net = solar_input // 10 - random.randint(2, 5)   # net mV change
        self.bat_mv = max(3000, min(4200, self.bat_mv + net))

    def reading(self) -> dict:
        """Generate a plausible set of sensor readings."""
        self.seq_num += 1
        self.drift()
        self.discharge()

        rng = random.Random()

        if self.oil_event:
            # Inject elevated oil and UV readings
            oil_raw   = rng.randint(90, 200)
            uv_raw    = rng.randint(130, 220)
            turbidity = rng.randint(30, 80)
            do_mgl    = rng.uniform(6.0, 10.0)
            ph        = rng.uniform(7.8, 8.4)
        elif self.bacteria_event:
            # Inject high turbidity and low DO (bacteria risk scenario)
            oil_raw   = rng.randint(0, 20)
            uv_raw    = rng.randint(0, 40)
            turbidity = rng.randint(160, 255)   # very turbid
            do_mgl    = rng.uniform(1.0, 3.5)   # low oxygen
            ph        = rng.uniform(5.8, 6.8)   # mildly acidic
        else:
            oil_raw   = rng.randint(0, 40)
            uv_raw    = rng.randint(0, 60)
            turbidity = rng.randint(5, 50)
            do_mgl    = rng.uniform(6.0, 10.0)
            ph        = rng.uniform(7.8, 8.4)

        temp_c = rng.uniform(14.0, 28.0)

        # Compute bacteria proxy (mirrors firmware/decoder formula, scaled 0-255)
        turb_norm    = turbidity / 255.0
        do_stress    = max(0.0, 1.0 - do_mgl / 10.0)
        ph_dev       = min(1.0, abs(ph - 7.0) / 4.0)
        bacteria_raw = int(min(255, (0.5 * turb_norm + 0.3 * do_stress + 0.2 * ph_dev) * 255))

        # Build alert flags
        alerts = 0
        if oil_raw   >= 70:  alerts |= (1 << 0)
        if uv_raw    >= 110: alerts |= (1 << 1)
        if turbidity >= 200 and ph > 6.0: alerts |= (1 << 2)
        if self.bat_mv < 3500: alerts |= (1 << 3)
        if bacteria_raw >= 80:   alerts |= (1 << 6)   # ALERT_BACTERIA

        # GPS always valid in simulation
        gps_flags = 0b111   # fix_ok + galileo + egnos

        return dict(
            buoy_id     = self.buoy_id,
            lat         = self.lat,
            lon         = self.lon,
            gps_flags   = gps_flags,
            bat_mv      = self.bat_mv,
            solar_pct   = self.solar_pct,
            temperature = int(temp_c),
            oil_raw     = oil_raw,
            uv_raw      = uv_raw,
            turbidity   = turbidity,
            ph_x10      = int(ph * 10),
            do_x10      = int(do_mgl * 10),
            alert_flags = alerts,
            seq_num     = self.seq_num,
        )


# ─── Seed factory (avoids mutable class-level default) ────────────────────
_SEEDS: list[tuple[float, float]] = [
    (12.57, 44.06),   # Rimini Beach
    (14.48, 40.63),   # Positano
    (7.27,  43.70),   # Nice
    (18.09, 42.65),   # Dubrovnik
    (3.07,  39.57),   # Mallorca
    (17.89, 40.25),   # Porto Cesareo
    (10.72, 45.63),   # Lake Garda
    (9.26,  46.00),   # Lake Como
    (12.10, 43.12),   # Lake Trasimeno
    (12.47, 41.89),   # Tiber River
    (12.25, 44.55),   # Po Delta
    (11.25, 43.77),   # Arno
    (4.83,  43.93),   # Rhone
    (16.02, 40.28),   # Pertusillo Dam
    (11.98, 43.94),   # Bilancino Dam
    (12.34, 46.27),   # Vajont
    (12.54, 41.86),   # Aqua Claudia
    (4.54,  43.94),   # Pont du Gard
    (-4.12, 40.95),   # Segovia
    (12.45, 37.50),   # Strait of Sicily
]


def _create_buoy(
    buoy_id: int,
    oil_event: bool = False,
    bacteria_event: bool = False,
) -> SimBuoy:
    lon, lat = _SEEDS[(buoy_id - 1) % len(_SEEDS)]
    return SimBuoy(
        buoy_id=buoy_id, lat=lat, lon=lon,
        oil_event=oil_event, bacteria_event=bacteria_event,
    )


# ─── Main simulation loop ─────────────────────────────────────────────────
def _send_reading(client: "httpx.Client", endpoint: str, buoy: SimBuoy) -> None:
    r = buoy.reading()
    raw = encode_packet(**r)
    hex_payload = raw.hex().upper()

    body = {
        "deviceId":    f"KIN{buoy.buoy_id:07d}",
        "timestamp":   datetime.utcnow().isoformat() + "Z",
        "payload":     hex_payload,
        "satelliteId": f"LEO-{random.randint(1, 18):02d}",
        "rssi":        round(random.uniform(-90, -65), 1),
        "doppler_lat": r["lat"] + random.gauss(0, 0.05),
        "doppler_lon": r["lon"] + random.gauss(0, 0.05),
    }

    try:
        resp = client.post(f"{endpoint}/api/iot/kineis/uplink", json=body, timeout=5.0)
        status = "[OK]" if resp.status_code == 200 else f"[{resp.status_code}]"
        alerts_str = ""
        if r["alert_flags"]:
            flags = []
            if r["alert_flags"] & (1 << 0): flags.append("OIL")
            if r["alert_flags"] & (1 << 1): flags.append("UV")
            if r["alert_flags"] & (1 << 2): flags.append("ALGAE")
            if r["alert_flags"] & (1 << 3): flags.append("LOW_BAT")
            if r["alert_flags"] & (1 << 6): flags.append("BACTERIA")
            alerts_str = f" ALERTS=[{','.join(flags)}]"
        print(
            f"{status} Buoy {buoy.buoy_id:3d} seq={r['seq_num']:5d} "
            f"pos=({r['lat']:.4f},{r['lon']:.4f}) "
            f"oil={r['oil_raw']:3d} uv={r['uv_raw']:3d} "
            f"bat={r['bat_mv']} mV"
            f"{alerts_str}"
        )
    except httpx.RequestError as exc:
        print(f"[ERR] Buoy {buoy.buoy_id}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AquaGuard buoy simulator")
    parser.add_argument("--buoys",     type=int, default=3,
                        help="Number of simulated buoys (default: 3)")
    parser.add_argument("--interval",  type=int, default=15,
                        help="Transmission interval in minutes (default: 15)")
    parser.add_argument("--endpoint",  default="http://localhost:8000",
                        help="Backend base URL")
    parser.add_argument("--once",      action="store_true",
                        help="Send one batch and exit")
    parser.add_argument("--oil-event",      action="store_true",
                        help="Inject oil spill on buoy 1")
    parser.add_argument("--bacteria-event", action="store_true",
                        help="Inject bacteria contamination event on buoy 2")
    args = parser.parse_args()

    buoys = [
        _create_buoy(
            i + 1,
            oil_event      = (args.oil_event and i == 0),
            bacteria_event = (args.bacteria_event and i == 1),
        )
        for i in range(args.buoys)
    ]

    print(f"AquaGuard buoy simulator — {len(buoys)} buoys — "
          f"interval {args.interval} min — endpoint {args.endpoint}")
    print("-" * 70)

    with httpx.Client() as client:
        cycle = 0
        while True:
            cycle += 1
            print(f"\n[Cycle {cycle}]  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
            for buoy in buoys:
                _send_reading(client, args.endpoint, buoy)

            if args.once:
                break

            sleep_s = args.interval * 60
            print(f"Next transmission in {args.interval} min…")
            time.sleep(sleep_s)


if __name__ == "__main__":
    main()
