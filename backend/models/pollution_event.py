"""Pydantic models for pollution events and trajectory predictions."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PollutionType(str, Enum):
    """Type of detected water pollution."""

    OIL_SPILL = "OIL_SPILL"
    ALGAL_BLOOM = "ALGAL_BLOOM"
    MARINE_DEBRIS = "MARINE_DEBRIS"
    HYDROCARBON = "HYDROCARBON"
    UNKNOWN = "UNKNOWN"


class Severity(str, Enum):
    """Severity level of a pollution event."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class BoundingBox(BaseModel):
    """Geographic bounding box for area-of-interest queries."""

    min_lon: float = Field(..., ge=-180, le=180)
    min_lat: float = Field(..., ge=-90, le=90)
    max_lon: float = Field(..., ge=-180, le=180)
    max_lat: float = Field(..., ge=-90, le=90)


class PollutionEvent(BaseModel):
    """A detected water pollution event derived from satellite imagery."""

    id: UUID = Field(default_factory=uuid4)
    event_type: PollutionType
    severity: Severity
    location: dict = Field(..., description="{'lon': float, 'lat': float}")
    area_km2: float = Field(..., ge=0)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    detected_at: datetime
    source_satellite: str
    mci_value: float | None = None
    vnri_value: float | None = None
    description: str = ""


class TrajectoryPoint(BaseModel):
    """Single particle position at a point in time."""

    lat: float
    lon: float
    timestamp: datetime


class TrajectoryPrediction(BaseModel):
    """Lagrangian trajectory forecast for a pollution event."""

    event_id: UUID
    particles: list[list[TrajectoryPoint]]
    uncertainty_radius_km: list[float]
    hours_predicted: int
