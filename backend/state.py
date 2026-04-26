"""Shared in-memory application state for the AquaGuard demo server."""

from typing import Any

app_state: dict[str, Any] = {
    # Satellite detection
    "events": [],
    "alerts": [],
    "subscriptions": [],
    # IoT buoy telemetry
    # buoy_telemetry: list[BuoyTelemetry] — all received records (capped at 500)
    "buoy_telemetry": [],
    # buoy_latest: dict[int, BuoyTelemetry] — most recent reading per buoy_id
    "buoy_latest": {},
    # buoy_locations: dict[int, tuple[str, str]] — (name, type) per buoy_id
    "buoy_locations": {},
}
