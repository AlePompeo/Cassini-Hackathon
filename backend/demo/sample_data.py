"""Synthetic demo data generator for AquaGuard hackathon demonstration.

Generates realistic pollution events spread across the Mediterranean Sea,
Adriatic, and Aegean basins — the primary operational domain for this project.
Also seeds demo buoy telemetry at coastal, lake, river, dam, and historic
aqueduct locations for the IoT monitoring layer.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from uuid import uuid4

from models.alert import Alert, AlertChannel, AlertPriority
from models.buoy import (
    AlertFlag,
    BuoyTelemetry,
    GpsInfo,
    PowerReadings,
    WaterReadings,
)
from models.pollution_event import PollutionEvent, PollutionType, Severity

# (lon, lat, zone_name) seeds for synthetic events
_MEDITERRANEAN_SEEDS: list[tuple[float, float, str]] = [
    (12.45, 37.50, "Strait of Sicily"),
    (14.22, 40.83, "Gulf of Naples"),
    (16.87, 41.12, "Southern Adriatic"),
    (13.50, 44.50, "Northern Adriatic"),
    (24.10, 37.90, "Aegean Sea"),
    (28.90, 41.00, "Marmara Approach"),
    (23.72, 38.00, "Cyclades"),
    (15.30, 38.10, "Messina Strait"),
    (17.20, 40.65, "Otranto Channel"),
    (12.00, 43.50, "Tyrrhenian Sea"),
    (9.50, 39.20, "Sardinia West"),
    (5.35, 43.30, "Gulf of Lion"),
    (2.10, 39.50, "Balearic Sea"),
    (-5.35, 36.00, "Gibraltar East"),
    (35.50, 36.80, "Levantine Basin"),
    (32.00, 31.50, "Nile Delta"),
    (23.50, 35.30, "Crete South"),
    (18.10, 42.40, "Dubrovnik Coast"),
    (13.70, 45.60, "Trieste Gulf"),
    (10.20, 44.10, "La Spezia Gulf"),
]


def _random_event(seed: tuple[float, float, str], idx: int) -> PollutionEvent:
    """Create a single synthetic PollutionEvent near a geographic seed."""
    rng = random.Random(idx * 31337)

    lon = seed[0] + rng.uniform(-0.5, 0.5)
    lat = seed[1] + rng.uniform(-0.3, 0.3)
    zone = seed[2]

    event_type = rng.choice(
        [
            PollutionType.OIL_SPILL,
            PollutionType.OIL_SPILL,
            PollutionType.ALGAL_BLOOM,
            PollutionType.HYDROCARBON,
            PollutionType.MARINE_DEBRIS,
        ]
    )

    area = rng.uniform(0.5, 85.0)

    if area > 50:
        severity = Severity.CRITICAL
    elif area > 20:
        severity = Severity.HIGH
    elif area > 5:
        severity = Severity.MEDIUM
    else:
        severity = Severity.LOW

    satellite = rng.choice(["Sentinel-1A", "Sentinel-1B", "Sentinel-2A", "Sentinel-2B"])
    hours_ago = rng.uniform(0.5, 72.0)
    detected_at = datetime.utcnow() - timedelta(hours=hours_ago)

    mci = None
    vnri = None
    if event_type in (PollutionType.OIL_SPILL, PollutionType.HYDROCARBON):
        vnri = rng.uniform(0.12, 0.42)
    if event_type == PollutionType.ALGAL_BLOOM:
        mci = rng.uniform(0.006, 0.035)

    descriptions = {
        PollutionType.OIL_SPILL: f"Oil slick detected near {zone}. "
        f"Estimated {area:.1f} km² affected. Possible tanker discharge.",
        PollutionType.ALGAL_BLOOM: f"Harmful algal bloom in {zone}. "
        f"Elevated chlorophyll-a. Beach advisory recommended.",
        PollutionType.HYDROCARBON: f"Hydrocarbon contamination in {zone}. "
        f"VNRI elevated. Source under investigation.",
        PollutionType.MARINE_DEBRIS: f"Marine debris accumulation in {zone}. "
        f"Likely plastic waste from coastal sources.",
        PollutionType.UNKNOWN: f"Anomalous reflectance signature in {zone}.",
    }

    return PollutionEvent(
        id=uuid4(),
        event_type=event_type,
        severity=severity,
        location={"lon": round(lon, 5), "lat": round(lat, 5)},
        area_km2=round(area, 2),
        confidence_score=round(rng.uniform(0.62, 0.98), 2),
        detected_at=detected_at,
        source_satellite=satellite,
        mci_value=round(mci, 4) if mci else None,
        vnri_value=round(vnri, 4) if vnri else None,
        description=descriptions[event_type],
    )


def generate_pollution_events(n: int = 20) -> list[PollutionEvent]:
    """Generate n realistic synthetic pollution events across the Mediterranean.

    Args:
        n: Number of events to generate (max 20 with distinct seed locations).

    Returns:
        List of PollutionEvent instances sorted by detected_at descending.
    """
    seeds = (_MEDITERRANEAN_SEEDS * 2)[:n]
    events = [_random_event(seed, idx) for idx, seed in enumerate(seeds)]
    return sorted(events, key=lambda e: e.detected_at, reverse=True)


def generate_alerts(events: list[PollutionEvent]) -> list[Alert]:
    """Generate Alert objects for HIGH and CRITICAL events.

    Args:
        events: Pollution events to generate alerts for.

    Returns:
        List of Alert instances for high-priority events.
    """
    alerts = []
    for event in events:
        if event.severity not in (Severity.HIGH, Severity.CRITICAL):
            continue

        priority = (
            AlertPriority.CRITICAL
            if event.severity == Severity.CRITICAL
            else AlertPriority.WARNING
        )
        zone = event.description.split("near ")[-1].split(".")[0]
        msg = (
            f"[{priority.value}] {event.event_type.value.replace('_', ' ').title()} "
            f"detected: {event.area_km2:.1f} km² in {zone}. "
            f"Confidence: {event.confidence_score:.0%}."
        )

        alerts.append(
            Alert(
                event_id=event.id,
                priority=priority,
                message=msg,
                recipients=["ops@aquaguard.eu", "coast.guard@example.it"],
                channels=[AlertChannel.EMAIL, AlertChannel.WEBHOOK],
                issued_at=event.detected_at,
                affected_zones=[zone],
            )
        )

    return alerts


# (lon, lat, name, location_type) for demo buoy seeding
_BUOY_SEEDS: list[tuple[float, float, str, str]] = [
    # Coastal Mediterranean beaches
    (12.57,  44.06, "Rimini Beach",        "COASTAL"),
    (14.48,  40.63, "Positano",            "COASTAL"),
    (7.27,   43.70, "Nice, Cote d'Azur",   "COASTAL"),
    (18.09,  42.65, "Dubrovnik",           "COASTAL"),
    (3.07,   39.57, "Alcudia, Mallorca",   "COASTAL"),
    (17.89,  40.25, "Porto Cesareo",       "COASTAL"),
    # Italian lakes
    (10.72,  45.63, "Lake Garda",          "LAKE"),
    (9.26,   46.00, "Lake Como",           "LAKE"),
    (12.10,  43.12, "Lake Trasimeno",      "LAKE"),
    (11.90,  42.60, "Lake Bolsena",        "LAKE"),
    # Rivers
    (12.47,  41.89, "Tiber River, Rome",   "RIVER"),
    (12.25,  44.55, "Po River Delta",      "RIVER"),
    (11.25,  43.77, "Arno, Florence",      "RIVER"),
    (4.83,   43.93, "Rhone, Avignon",      "RIVER"),
    # Dams and reservoirs
    (16.02,  40.28, "Lago del Pertusillo", "DAM"),
    (11.98,  43.94, "Lago di Bilancino",   "DAM"),
    (12.34,  46.27, "Lago del Vajont",     "DAM"),
    # Roman aqueducts / historic water infrastructure
    (12.54,  41.86, "Aqua Claudia, Rome",  "AQUEDUCT"),
    (4.54,   43.94, "Pont du Gard",        "AQUEDUCT"),
    (-4.12,  40.95, "Segovia Aqueduct",    "AQUEDUCT"),
]


def _make_buoy_readings(
    rng: random.Random,
    buoy_id: int,
    lat: float,
    lon: float,
    loc_type: str,
    hours_ago_start: float,
    n_readings: int,
    inject_bacteria: bool = False,
    inject_oil: bool = False,
) -> list[BuoyTelemetry]:
    """Generate n_readings of synthetic telemetry for one demo buoy.

    Args:
        rng: Seeded random number generator.
        buoy_id: Buoy identifier (1–254).
        lat: Seed latitude.
        lon: Seed longitude.
        loc_type: Location category (COASTAL, LAKE, RIVER, DAM, AQUEDUCT).
        hours_ago_start: Age in hours of the oldest reading.
        n_readings: Number of telemetry records to create.
        inject_bacteria: If True, elevate bacteria proxy values.
        inject_oil: If True, elevate oil/UV readings.

    Returns:
        List of BuoyTelemetry objects, oldest first.
    """
    records: list[BuoyTelemetry] = []
    bat_mv = rng.randint(3600, 4100)
    seq = 0

    for i in range(n_readings):
        seq += 1
        age_h = hours_ago_start - i * (hours_ago_start / max(1, n_readings - 1))
        ts = datetime.utcnow() - timedelta(hours=age_h)

        # Drift position slightly
        cur_lat = lat + rng.gauss(0, 0.001) * i
        cur_lon = lon + rng.gauss(0, 0.001) * i

        # Sensor readings vary by location type
        if loc_type in ("RIVER", "DAM"):
            turb_ntu = rng.uniform(20, 120)
            ph       = rng.uniform(7.0, 8.2)
            do_mgl   = rng.uniform(5.0, 9.5)
        elif loc_type == "LAKE":
            turb_ntu = rng.uniform(5, 60)
            ph       = rng.uniform(7.5, 9.0)
            do_mgl   = rng.uniform(6.0, 11.0)
        elif loc_type == "AQUEDUCT":
            turb_ntu = rng.uniform(2, 30)
            ph       = rng.uniform(6.8, 7.8)
            do_mgl   = rng.uniform(7.0, 12.0)
        else:  # COASTAL
            turb_ntu = rng.uniform(3, 40)
            ph       = rng.uniform(7.8, 8.4)
            do_mgl   = rng.uniform(6.5, 10.5)

        if inject_bacteria:
            turb_ntu = max(turb_ntu, rng.uniform(150, 350))
            do_mgl   = min(do_mgl, rng.uniform(1.0, 4.0))

        oil_raw = rng.randint(80, 160) if inject_oil else rng.randint(0, 30)
        uv_raw  = rng.randint(100, 180) if inject_oil else rng.randint(0, 50)
        turb_raw = int(min(255, turb_ntu / 10))

        # Compute bacteria estimate
        _tf = min(1.0, turb_ntu / 500.0) * 0.5
        _df = max(0.0, 1.0 - do_mgl / 10.0) * 0.3
        _pf = min(1.0, abs(ph - 7.0) / 4.0) * 0.2
        bacteria_est = round(min(1.0, _tf + _df + _pf), 3)

        # Alert flags
        alert_flags: list[AlertFlag] = []
        if oil_raw >= 70:   alert_flags.append(AlertFlag.OIL)
        if uv_raw >= 110:   alert_flags.append(AlertFlag.UV)
        if bacteria_est > (80 / 255): alert_flags.append(AlertFlag.BACTERIA)
        if bat_mv < 3500:   alert_flags.append(AlertFlag.LOW_BAT)

        solar_pct = rng.randint(20, 90)
        bat_mv = max(3100, min(4200, bat_mv + rng.randint(-10, 15)))

        records.append(
            BuoyTelemetry(
                buoy_id    = buoy_id,
                received_at = ts,
                seq_num    = seq,
                latitude   = round(cur_lat, 5),
                longitude  = round(cur_lon, 5),
                gps        = GpsInfo(
                    fix_ok=True, galileo_used=True, egnos_active=True, satellites=8
                ),
                water = WaterReadings(
                    temperature_c = round(rng.uniform(10.0, 25.0), 1),
                    oil_raw       = oil_raw,
                    uv_raw        = uv_raw,
                    turbidity_ntu = round(turb_ntu, 1),
                    ph            = round(ph, 1),
                    do_mgl        = round(do_mgl, 1),
                    bacteria_est  = bacteria_est,
                ),
                power = PowerReadings(
                    bat_mv      = bat_mv,
                    solar_pct   = solar_pct,
                    low_battery = bat_mv < 3500,
                ),
                alerts  = alert_flags,
                raw_hex = "",
            )
        )

    return records


def generate_demo_buoys() -> tuple[
    list[BuoyTelemetry], dict[int, BuoyTelemetry], dict[int, tuple[str, str]]
]:
    """Seed demo buoy telemetry at coastal, lake, river, dam, and aqueduct sites.

    Returns:
        Tuple of (all_telemetry_records, latest_per_buoy_dict, locations_dict)
        for direct insertion into app_state. locations_dict maps buoy_id to
        (location_name, location_type).
    """
    all_telemetry: list[BuoyTelemetry] = []
    latest: dict[int, BuoyTelemetry] = {}
    locations: dict[int, tuple[str, str]] = {}

    for idx, (lon, lat, name, loc_type) in enumerate(_BUOY_SEEDS):
        buoy_id = idx + 1
        locations[buoy_id] = (name, loc_type)
        rng = random.Random(buoy_id * 97531)
        n = rng.randint(8, 24)

        inject_bacteria = buoy_id in (7, 11, 15)   # Garda, Tiber, Pertusillo
        inject_oil      = buoy_id in (1, 5)         # Rimini, Mallorca

        records = _make_buoy_readings(
            rng           = rng,
            buoy_id       = buoy_id,
            lat           = lat,
            lon           = lon,
            loc_type      = loc_type,
            hours_ago_start = rng.uniform(4.0, 24.0),
            n_readings    = n,
            inject_bacteria = inject_bacteria,
            inject_oil    = inject_oil,
        )

        # Buoy 17 (Vajont) is offline — backdate its last reading
        if buoy_id == 17:
            for r in records:
                r.received_at -= timedelta(hours=6)

        all_telemetry.extend(records)
        latest[buoy_id] = max(records, key=lambda r: r.received_at)

    return all_telemetry, latest, locations
