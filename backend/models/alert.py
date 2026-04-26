"""Pydantic models for alerts and subscriptions."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AlertChannel(str, Enum):
    """Notification delivery channel."""

    EMAIL = "EMAIL"
    SMS = "SMS"
    WEBHOOK = "WEBHOOK"
    PUSH = "PUSH"


class AlertPriority(str, Enum):
    """Priority level of an alert."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class Alert(BaseModel):
    """An alert issued in response to a detected pollution event."""

    id: UUID = Field(default_factory=uuid4)
    event_id: UUID
    priority: AlertPriority
    message: str
    recipients: list[str] = Field(default_factory=list)
    channels: list[AlertChannel] = Field(default_factory=list)
    issued_at: datetime = Field(default_factory=datetime.utcnow)
    affected_zones: list[str] = Field(default_factory=list)


class Subscription(BaseModel):
    """Alert subscription for a zone and set of pollution types."""

    id: UUID = Field(default_factory=uuid4)
    email: str
    zones: list[str] = Field(default_factory=list)
    alert_types: list[str] = Field(default_factory=list)
    min_severity: str = "LOW"
