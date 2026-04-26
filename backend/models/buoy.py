"""Pydantic models for AquaGuard smart buoy telemetry."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AlertFlag(str, Enum):
    """Alert types reported by the buoy firmware."""

    OIL        = "OIL"
    UV         = "UV"
    ALGAE      = "ALGAE"
    LOW_BAT    = "LOW_BAT"
    GPS_FAIL   = "GPS_FAIL"
    SENSOR_ERR = "SENSOR_ERR"
    BACTERIA   = "BACTERIA"


# Bit positions in the firmware alert_flags byte
_ALERT_BIT: dict[int, AlertFlag] = {
    0: AlertFlag.OIL,
    1: AlertFlag.UV,
    2: AlertFlag.ALGAE,
    3: AlertFlag.LOW_BAT,
    4: AlertFlag.GPS_FAIL,
    5: AlertFlag.SENSOR_ERR,
    6: AlertFlag.BACTERIA,
}


def decode_alert_flags(raw: int) -> list[AlertFlag]:
    """Decode the 8-bit alert_flags byte into a list of AlertFlag values."""
    return [flag for bit, flag in _ALERT_BIT.items() if raw & (1 << bit)]


class GpsInfo(BaseModel):
    """GPS fix metadata from the buoy."""

    fix_ok: bool
    galileo_used: bool
    egnos_active: bool
    satellites: int = 0


class WaterReadings(BaseModel):
    """Decoded water quality sensor values."""

    temperature_c: float = Field(..., description="Water temperature (°C)")
    oil_raw: int = Field(..., ge=0, le=255, description="Oil film sensor 0–255")
    uv_raw: int = Field(..., ge=0, le=255, description="UV fluorescence 0–255")
    turbidity_ntu: float = Field(..., ge=0, description="Turbidity (NTU)")
    ph: float = Field(..., ge=0.0, le=14.0, description="Water pH")
    do_mgl: float = Field(..., ge=0.0, description="Dissolved oxygen (mg/L)")
    bacteria_est: float = Field(
        0.0, ge=0.0, le=1.0,
        description=(
            "Estimated bacteria contamination risk 0–1 "
            "(proxy: turbidity 50%, low-DO 30%, pH-deviation 20%)"
        ),
    )
    sensor_error: bool = Field(False, description="True if any sensor reading failed")


class PowerReadings(BaseModel):
    """Battery and solar power status from the buoy."""

    bat_mv: int = Field(..., ge=0, description="Battery voltage (mV)")
    solar_pct: int = Field(..., ge=0, le=100, description="Solar charge level (%)")
    low_battery: bool = False


class BuoyTelemetry(BaseModel):
    """A single telemetry record received from a buoy via Kinéis uplink."""

    id: UUID = Field(default_factory=uuid4)
    buoy_id: int = Field(..., ge=1, le=254)
    received_at: datetime = Field(default_factory=datetime.utcnow)
    seq_num: int = Field(..., ge=0, le=65535, description="Rolling packet sequence number")

    # Position
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    gps: GpsInfo

    # Sensor readings
    water: WaterReadings
    power: PowerReadings

    # Active alerts decoded from the firmware flag byte
    alerts: list[AlertFlag] = Field(default_factory=list)

    # Raw hex payload as received from Kinéis (for audit trail)
    raw_hex: str = ""

    # Kinéis metadata forwarded by the platform webhook
    kineis_device_id: str = ""
    satellite_id: str = ""


class BuoyOperationalState(str, Enum):
    """Operational state of a deployed buoy unit."""

    UP      = "UP"       # fully operational
    DOWN    = "DOWN"     # offline or sensor malfunction — needs attention
    REPLACE = "REPLACE"  # critically low battery or persistent hardware failure


class SensorHealth(BaseModel):
    """Per-sensor quality score (0 = failed, 1 = perfect) for a buoy."""

    oil:              float = Field(1.0, ge=0.0, le=1.0)
    uv:               float = Field(1.0, ge=0.0, le=1.0)
    turbidity:        float = Field(1.0, ge=0.0, le=1.0)
    ph:               float = Field(1.0, ge=0.0, le=1.0)
    dissolved_oxygen: float = Field(1.0, ge=0.0, le=1.0)
    bacteria:         float = Field(1.0, ge=0.0, le=1.0)
    gps:              float = Field(1.0, ge=0.0, le=1.0)


class BuoyHealth(BaseModel):
    """Aggregated health and reliability metrics for a single buoy."""

    operational_state: BuoyOperationalState = Field(
        ..., description="Current operational state of the buoy"
    )
    sensor_quality: SensorHealth = Field(
        default_factory=SensorHealth,
        description="Quality score per sensor derived from recent reading history",
    )
    false_positive_rate: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Fraction of isolated single-reading alert spikes vs sustained alerts",
    )
    uptime_pct: float = Field(
        100.0, ge=0.0, le=100.0,
        description="Estimated uptime: received readings vs expected at 15-min intervals",
    )


class RiskCategory(str, Enum):
    """Environmental risk band used for insurance and real-estate underwriting."""

    VERY_LOW  = "VERY_LOW"
    LOW       = "LOW"
    MODERATE  = "MODERATE"
    HIGH      = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class RiskProfile(BaseModel):
    """Composite environmental risk index for insurance and real-estate assessment.

    Combines pollution alert history, sensor-derived water quality, and
    infrastructure reliability into a single 0–100 score with three
    weighted sub-components:
      - pollution_risk     (40%) — frequency of OIL / BACTERIA / ALGAE alerts
      - water_quality_risk (40%) — bacteria proxy, turbidity, DO, pH stress
      - infrastructure_risk(20%) — location-type baseline + uptime penalty
    """

    overall_score: float = Field(
        ..., ge=0.0, le=100.0,
        description="Weighted composite risk 0–100 (higher = greater environmental liability)",
    )
    category: RiskCategory
    pollution_risk: float = Field(
        ..., ge=0.0, le=100.0,
        description="Alert-frequency sub-score (40% weight in overall)",
    )
    water_quality_risk: float = Field(
        ..., ge=0.0, le=100.0,
        description="Sensor-derived water quality sub-score (40% weight)",
    )
    infrastructure_risk: float = Field(
        ..., ge=0.0, le=100.0,
        description="Location-type + uptime reliability sub-score (20% weight)",
    )
    trend: str = Field(
        ..., description="Bacteria/alert trend over the available window: IMPROVING | STABLE | DEGRADING",
    )
    insurer_note: str = Field(
        ..., description="Plain-language one-line summary for property underwriters",
    )


class BuoyStatus(BaseModel):
    """Aggregated health status for a single buoy (computed on the backend)."""

    buoy_id: int
    last_seen: datetime
    last_latitude: float
    last_longitude: float
    bat_mv: int
    solar_pct: int
    active_alerts: list[AlertFlag]
    total_readings: int
    online: bool = Field(
        description="True if last telemetry was received within 30 minutes",
    )
    health: Optional[BuoyHealth] = Field(
        None,
        description="Health metrics — available once ≥5 readings exist for this buoy",
    )
    location_name: str = Field("", description="Human-readable location name (e.g. 'Lake Garda')")
    location_type: str = Field("", description="Location category: COASTAL, LAKE, RIVER, DAM, AQUEDUCT")
    risk_profile: Optional[RiskProfile] = Field(
        None,
        description="Insurance risk index — available once ≥5 readings exist for this buoy",
    )
