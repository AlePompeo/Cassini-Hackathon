"""AquaGuard FastAPI application entry point.

Run with:
    python main.py
or:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import alerts_router, buoys_router, detection_router, kineis_router, trajectory_router
from demo.sample_data import generate_alerts, generate_demo_buoys, generate_pollution_events
from state import app_state

app = FastAPI(
    title="AquaGuard API",
    description=(
        "Real-time water pollution monitoring using Copernicus satellite data. "
        "Detects oil spills, algal blooms, and marine debris via Sentinel-1/2."
    ),
    version="0.1.0",
    contact={"name": "AquaGuard Team", "email": "team@aquaguard.eu"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(detection_router)
app.include_router(trajectory_router)
app.include_router(alerts_router)
app.include_router(buoys_router)
app.include_router(kineis_router)


@app.on_event("startup")
async def populate_demo_data() -> None:
    """Seed the in-memory store with synthetic events on server start."""
    events = generate_pollution_events(n=20)
    alerts = generate_alerts(events)
    buoy_telemetry, buoy_latest, buoy_locations = generate_demo_buoys()
    app_state["events"] = events
    app_state["alerts"] = alerts
    app_state["buoy_telemetry"] = buoy_telemetry
    app_state["buoy_latest"] = buoy_latest
    app_state["buoy_locations"] = buoy_locations
    print(
        f"[AquaGuard] Demo data loaded: "
        f"{len(events)} events, {len(alerts)} alerts, "
        f"{len(buoy_latest)} buoys ({len(buoy_telemetry)} readings)."
    )


@app.get("/", tags=["health"])
async def root() -> dict:
    """Health check endpoint."""
    return {
        "service": "AquaGuard",
        "status": "operational",
        "version": "0.1.0",
        "description": "Real-time water pollution monitoring via Copernicus + Galileo",
    }


@app.get("/api/status", tags=["health"])
async def status() -> dict:
    """Return summary statistics for the dashboard status bar."""
    from models.pollution_event import Severity

    critical = sum(
        1 for e in app_state["events"] if e.severity == Severity.CRITICAL
    )
    from datetime import timedelta

    online_cutoff = __import__("datetime").datetime.utcnow() - timedelta(minutes=30)
    buoys_online = sum(
        1 for t in app_state["buoy_latest"].values()
        if t.received_at > online_cutoff
    )

    return {
        "total_events": len(app_state["events"]),
        "active_alerts": len(app_state["alerts"]),
        "zones_monitored": 10,
        "critical_events": critical,
        "satellites_active": ["Sentinel-1A", "Sentinel-1B", "Sentinel-2A", "Sentinel-2B"],
        "buoys_online": buoys_online,
        "buoys_total": len(app_state["buoy_latest"]),
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
