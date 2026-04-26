"""Buoy fleet management API endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query

from models.buoy import (
    AlertFlag,
    BuoyHealth,
    BuoyOperationalState,
    BuoyStatus,
    BuoyTelemetry,
    RiskCategory,
    RiskProfile,
    SensorHealth,
)
from state import app_state

router = APIRouter(prefix="/api/buoys", tags=["iot"])

_ONLINE_THRESHOLD_MINUTES = 30
_MIN_HEALTH_READINGS = 5   # minimum readings before computing health metrics


def _compute_health(
    latest: BuoyTelemetry,
    history: list[BuoyTelemetry],
    online: bool,
) -> BuoyHealth:
    """Derive health metrics for a buoy from its telemetry history.

    Args:
        latest: Most recent telemetry record.
        history: All stored telemetry for this buoy (any order).
        online: Whether the buoy is currently considered online.

    Returns:
        BuoyHealth with operational state, per-sensor quality, false positive
        rate, and uptime estimate.
    """
    # Operational state
    if latest.power.bat_mv < 3200:
        state = BuoyOperationalState.REPLACE
    elif not online or latest.water.sensor_error:
        state = BuoyOperationalState.DOWN
    else:
        state = BuoyOperationalState.UP

    # Uptime: compare received readings to expected rate (1 per 15 min)
    if len(history) >= 2:
        sorted_h = sorted(history, key=lambda t: t.received_at)
        span_s = (sorted_h[-1].received_at - sorted_h[0].received_at).total_seconds()
        expected = max(1.0, span_s / (15 * 60))
        uptime_pct = round(min(100.0, len(history) / expected * 100.0), 1)
    else:
        uptime_pct = 100.0

    # Per-sensor quality using the 20 most recent readings
    recent = sorted(history, key=lambda t: t.received_at, reverse=True)[:20]

    def _in_range_score(values: list[float], lo: float, hi: float) -> float:
        if not values:
            return 1.0
        return sum(1 for v in values if lo <= v <= hi) / len(values)

    ph_q   = _in_range_score([t.water.ph for t in recent], 6.0, 9.5)
    do_q   = _in_range_score([t.water.do_mgl for t in recent], 1.0, 20.0)
    gps_q  = sum(1 for t in recent if t.gps.fix_ok) / max(1, len(recent))
    err_q  = 1.0 - sum(1 for t in recent if t.water.sensor_error) / max(1, len(recent))

    sensor_quality = SensorHealth(
        oil=err_q,
        uv=err_q,
        turbidity=round(min(1.0, (ph_q + do_q) / 2.0 + 0.1), 2),
        ph=round(ph_q, 2),
        dissolved_oxygen=round(do_q, 2),
        bacteria=round((ph_q + do_q) / 2.0, 2),
        gps=round(gps_q, 2),
    )

    # False positive rate: isolated single-reading alert spikes
    alerts_seq = [bool(t.alerts) for t in recent]
    spikes = 0
    total_alerts = sum(alerts_seq)
    if len(alerts_seq) >= 3:
        for i in range(1, len(alerts_seq) - 1):
            if alerts_seq[i] and not alerts_seq[i - 1] and not alerts_seq[i + 1]:
                spikes += 1
    fp_rate = round(spikes / max(1, total_alerts), 3) if total_alerts > 0 else 0.0

    return BuoyHealth(
        operational_state=state,
        sensor_quality=sensor_quality,
        false_positive_rate=fp_rate,
        uptime_pct=uptime_pct,
    )


# Base environmental risk contribution by location type (0–100 scale)
_LOC_TYPE_BASE_RISK: dict[str, float] = {
    "COASTAL":  10.0,
    "LAKE":     15.0,
    "RIVER":    30.0,
    "DAM":      25.0,
    "AQUEDUCT": 10.0,
}

_POLLUTION_FLAGS = {AlertFlag.OIL, AlertFlag.UV, AlertFlag.BACTERIA, AlertFlag.ALGAE}


def _compute_risk_profile(
    history: list[BuoyTelemetry],
    health: Optional[BuoyHealth],
    loc_type: str,
    loc_name: str,
) -> RiskProfile:
    """Derive an insurance-grade risk index from telemetry history.

    Args:
        history: All stored telemetry for this buoy (any order).
        health:  Pre-computed BuoyHealth (or None if insufficient history).
        loc_type: Location category string (COASTAL, LAKE, RIVER, DAM, AQUEDUCT).
        loc_name: Human-readable location name used in the insurer note.

    Returns:
        RiskProfile with three sub-scores, an overall 0–100 score,
        a risk category, a trend, and a plain-language insurer note.
    """
    recent = sorted(history, key=lambda t: t.received_at, reverse=True)[:20]
    n = len(recent)

    # ── Pollution risk (40% weight) ──────────────────────────────────────────
    # Frequency of readings with at least one pollution alert flag
    poll_readings = sum(
        1 for t in recent if any(f in _POLLUTION_FLAGS for f in t.alerts)
    )
    poll_freq = poll_readings / max(1, n)
    # Recent 5-reading spike rate weighted higher
    last5_poll = sum(
        1 for t in recent[:5] if any(f in _POLLUTION_FLAGS for f in t.alerts)
    ) / max(1, min(5, n))
    pollution_risk = round(min(100.0, (0.55 * poll_freq + 0.45 * last5_poll) * 100.0), 1)

    # ── Water quality risk (40% weight) ──────────────────────────────────────
    if recent:
        avg_bact  = sum(t.water.bacteria_est for t in recent) / n
        avg_turb  = sum(min(1.0, t.water.turbidity_ntu / 200.0) for t in recent) / n
        avg_do    = sum(max(0.0, 1.0 - t.water.do_mgl / 8.0) for t in recent) / n
        avg_ph    = sum(min(1.0, abs(t.water.ph - 7.0) / 3.0) for t in recent) / n
        wq_raw    = 0.35 * avg_bact + 0.25 * avg_turb + 0.25 * avg_do + 0.15 * avg_ph
        water_quality_risk = round(min(100.0, wq_raw * 100.0), 1)
    else:
        water_quality_risk = 0.0

    # ── Infrastructure risk (20% weight) ─────────────────────────────────────
    loc_base   = _LOC_TYPE_BASE_RISK.get(loc_type, 15.0)
    uptime_pen = (1.0 - (health.uptime_pct / 100.0)) * 40.0 if health else 20.0
    fp_pen     = (health.false_positive_rate * 20.0) if health else 0.0
    infrastructure_risk = round(min(100.0, loc_base + uptime_pen + fp_pen), 1)

    # ── Overall ───────────────────────────────────────────────────────────────
    overall = round(
        0.40 * pollution_risk + 0.40 * water_quality_risk + 0.20 * infrastructure_risk, 1
    )

    if overall < 20:
        category = RiskCategory.VERY_LOW
    elif overall < 40:
        category = RiskCategory.LOW
    elif overall < 60:
        category = RiskCategory.MODERATE
    elif overall < 80:
        category = RiskCategory.HIGH
    else:
        category = RiskCategory.VERY_HIGH

    # ── Trend ─────────────────────────────────────────────────────────────────
    trend = "STABLE"
    if n >= 6:
        mid   = n // 2
        older = recent[mid:]   # older half (list is newest-first)
        newer = recent[:mid]   # newer half
        old_bact = sum(t.water.bacteria_est for t in older) / len(older)
        new_bact = sum(t.water.bacteria_est for t in newer) / len(newer)
        delta = new_bact - old_bact
        if delta < -0.05:
            trend = "IMPROVING"
        elif delta > 0.05:
            trend = "DEGRADING"

    # ── Insurer note ─────────────────────────────────────────────────────────
    loc_label = {
        "COASTAL":  "coastal property",
        "LAKE":     "lakefront property",
        "RIVER":    "riverbank property",
        "DAM":      "reservoir-adjacent property",
        "AQUEDUCT": "historic water infrastructure site",
    }.get(loc_type, "nearby property")

    note_map = {
        RiskCategory.VERY_LOW: (
            f"Clean water history at {loc_name}. "
            f"Minimal environmental liability for {loc_label} — standard policy terms apply."
        ),
        RiskCategory.LOW: (
            f"Generally good quality at {loc_name} with minor anomalies. "
            f"Low environmental premium for {loc_label} recommended."
        ),
        RiskCategory.MODERATE: (
            f"Moderate contamination events at {loc_name}. "
            f"Environmental liability rider advised before insuring {loc_label}."
        ),
        RiskCategory.HIGH: (
            f"Frequent pollution alerts at {loc_name}. "
            f"Elevated premium required; independent environmental assessment "
            f"recommended prior to underwriting {loc_label}."
        ),
        RiskCategory.VERY_HIGH: (
            f"Critical contamination history at {loc_name}. "
            f"High-risk classification — specialist underwriting and site remediation "
            f"assessment mandatory for {loc_label}."
        ),
    }

    return RiskProfile(
        overall_score      = overall,
        category           = category,
        pollution_risk     = pollution_risk,
        water_quality_risk = water_quality_risk,
        infrastructure_risk= infrastructure_risk,
        trend              = trend,
        insurer_note       = note_map[category],
    )


@router.get("/", response_model=list[BuoyStatus])
async def list_buoys() -> list[BuoyStatus]:
    """Return aggregated status for every known buoy.

    A buoy is considered 'online' if its last telemetry was received within
    the past 30 minutes.
    """
    cutoff = datetime.utcnow() - timedelta(minutes=_ONLINE_THRESHOLD_MINUTES)
    statuses: list[BuoyStatus] = []

    for buoy_id, latest in app_state["buoy_latest"].items():
        history = [t for t in app_state["buoy_telemetry"] if t.buoy_id == buoy_id]
        online = latest.received_at > cutoff

        health = (
            _compute_health(latest, history, online)
            if len(history) >= _MIN_HEALTH_READINGS
            else None
        )

        loc_name, loc_type = app_state["buoy_locations"].get(buoy_id, ("", ""))

        risk_profile = (
            _compute_risk_profile(history, health, loc_type, loc_name)
            if len(history) >= _MIN_HEALTH_READINGS
            else None
        )

        statuses.append(
            BuoyStatus(
                buoy_id        = buoy_id,
                last_seen      = latest.received_at,
                last_latitude  = latest.latitude,
                last_longitude = latest.longitude,
                bat_mv         = latest.power.bat_mv,
                solar_pct      = latest.power.solar_pct,
                active_alerts  = latest.alerts,
                total_readings = len(history),
                online         = online,
                health         = health,
                location_name  = loc_name,
                location_type  = loc_type,
                risk_profile   = risk_profile,
            )
        )

    return sorted(statuses, key=lambda s: s.buoy_id)


@router.get("/{buoy_id}", response_model=BuoyStatus)
async def get_buoy(buoy_id: int) -> BuoyStatus:
    """Return the current status of a single buoy.

    Raises:
        HTTPException: 404 if no telemetry has been received for this buoy.
    """
    latest = app_state["buoy_latest"].get(buoy_id)
    if latest is None:
        raise HTTPException(status_code=404, detail=f"Buoy {buoy_id} not found.")

    cutoff = datetime.utcnow() - timedelta(minutes=_ONLINE_THRESHOLD_MINUTES)
    history = [t for t in app_state["buoy_telemetry"] if t.buoy_id == buoy_id]
    online = latest.received_at > cutoff

    health = (
        _compute_health(latest, history, online)
        if len(history) >= _MIN_HEALTH_READINGS
        else None
    )

    loc_name, loc_type = app_state["buoy_locations"].get(buoy_id, ("", ""))

    risk_profile = (
        _compute_risk_profile(history, health, loc_type, loc_name)
        if len(history) >= _MIN_HEALTH_READINGS
        else None
    )

    return BuoyStatus(
        buoy_id        = buoy_id,
        last_seen      = latest.received_at,
        last_latitude  = latest.latitude,
        last_longitude = latest.longitude,
        bat_mv         = latest.power.bat_mv,
        solar_pct      = latest.power.solar_pct,
        active_alerts  = latest.alerts,
        total_readings = len(history),
        online         = online,
        health         = health,
        location_name  = loc_name,
        location_type  = loc_type,
        risk_profile   = risk_profile,
    )


@router.get("/{buoy_id}/history", response_model=list[BuoyTelemetry])
async def get_buoy_history(
    buoy_id: int,
    limit: int = Query(50, ge=1, le=200),
) -> list[BuoyTelemetry]:
    """Return the most recent telemetry records for a buoy, newest first.

    Args:
        buoy_id: Buoy identifier (1–254).
        limit: Maximum number of records to return.
    """
    records = [
        t for t in app_state["buoy_telemetry"] if t.buoy_id == buoy_id
    ]
    if not records:
        raise HTTPException(status_code=404, detail=f"No history for buoy {buoy_id}.")

    return sorted(records, key=lambda t: t.received_at, reverse=True)[:limit]
