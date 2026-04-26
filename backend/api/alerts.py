"""Alerts and subscription management API endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

from models.alert import Alert, AlertChannel, AlertPriority, Subscription
from state import app_state

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

# Available monitoring zones
_ZONES = [
    "Strait of Sicily",
    "Gulf of Naples",
    "Southern Adriatic",
    "Northern Adriatic",
    "Aegean Sea",
    "Cyclades",
    "Tyrrhenian Sea",
    "Balearic Sea",
    "Levantine Basin",
    "Gulf of Lion",
]


class SubscribeRequest(BaseModel):
    """Body for POST /api/alerts/subscribe."""

    email: str
    zones: list[str] = []
    alert_types: list[str] = []
    min_severity: str = "MEDIUM"


@router.get("/", response_model=list[Alert])
async def list_alerts(limit: int = 20) -> list[Alert]:
    """Return the most recent alerts, newest first.

    Args:
        limit: Maximum alerts to return.
    """
    return sorted(
        app_state["alerts"],
        key=lambda a: a.issued_at,
        reverse=True,
    )[:limit]


@router.post("/subscribe", response_model=Subscription)
async def subscribe(body: SubscribeRequest) -> Subscription:
    """Create a new alert subscription.

    The subscriber will receive notifications when events matching their
    zone and severity criteria are detected.
    """
    sub = Subscription(
        email=body.email,
        zones=body.zones or _ZONES,
        alert_types=body.alert_types,
        min_severity=body.min_severity,
    )
    app_state["subscriptions"].append(sub)
    return sub


@router.get("/zones", response_model=list[str])
async def list_zones() -> list[str]:
    """Return the list of available monitoring zones."""
    return _ZONES
