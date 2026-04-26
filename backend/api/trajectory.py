"""Trajectory prediction API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from models.pollution_event import TrajectoryPoint, TrajectoryPrediction
from processing.trajectory import LagrangianTracker
from state import app_state

router = APIRouter(prefix="/api/trajectory", tags=["trajectory"])

_tracker = LagrangianTracker(rng_seed=42)


class TrajectoryRequest(BaseModel):
    """Request body for trajectory prediction."""

    lon: float
    lat: float
    wind_u: float = 4.0
    wind_v: float = 1.5
    current_u: float = 0.15
    current_v: float = 0.08
    duration_hours: int = 48
    n_particles: int = 100


@router.post("/predict", response_model=TrajectoryPrediction)
async def predict_trajectory(body: TrajectoryRequest) -> TrajectoryPrediction:
    """Run a Lagrangian trajectory forecast from a given spill location.

    Returns particle positions at hourly intervals for the requested
    forecast horizon.
    """
    result = _tracker.run(
        spill_lon=body.lon,
        spill_lat=body.lat,
        u_wind=body.wind_u,
        v_wind=body.wind_v,
        u_current=body.current_u,
        v_current=body.current_v,
        duration_hours=body.duration_hours,
        n_particles=body.n_particles,
    )

    # Subsample: return every 6th time step to keep response lean
    step = 6
    indices = list(range(0, result.n_timesteps, step))

    particles: list[list[TrajectoryPoint]] = []
    for p_idx in range(min(body.n_particles, 20)):  # cap output at 20 particles
        track = [
            TrajectoryPoint(
                lat=round(float(result.particles_lat[p_idx, t]), 5),
                lon=round(float(result.particles_lon[p_idx, t]), 5),
                timestamp=result.timesteps[t],
            )
            for t in indices
        ]
        particles.append(track)

    uncertainty = [result.uncertainty_radius_km[t] for t in indices]

    return TrajectoryPrediction(
        event_id=UUID("00000000-0000-0000-0000-000000000000"),
        particles=particles,
        uncertainty_radius_km=uncertainty,
        hours_predicted=body.duration_hours,
    )


_FORECAST_HORIZONS = [2, 4, 6, 24, 48]


@router.get("/horizons/{event_id}", tags=["trajectory"])
async def multi_horizon_forecast(
    event_id: UUID,
    wind_u: float = Query(4.0, description="Eastward wind component (m/s)"),
    wind_v: float = Query(1.5, description="Northward wind component (m/s)"),
    current_u: float = Query(0.15, description="Eastward surface current (m/s)"),
    current_v: float = Query(0.08, description="Northward surface current (m/s)"),
) -> dict:
    """Return trajectory forecasts for multiple standard horizons: 2h, 4h, 6h, 24h, 48h.

    Designed for the pitch dashboard timeline slider. Each key in the response
    maps a horizon label to its TrajectoryPrediction. The event location is
    looked up from the in-memory store.

    Raises:
        HTTPException: 404 if the event is not found.
    """
    event = next((e for e in app_state["events"] if e.id == event_id), None)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found.")

    forecasts: dict[str, dict] = {}
    for hours in _FORECAST_HORIZONS:
        req = TrajectoryRequest(
            lon=event.location["lon"],
            lat=event.location["lat"],
            wind_u=wind_u,
            wind_v=wind_v,
            current_u=current_u,
            current_v=current_v,
            duration_hours=hours,
            n_particles=100,
        )
        prediction = await predict_trajectory(req)
        prediction.event_id = event_id
        forecasts[f"{hours}h"] = prediction.model_dump()

    return forecasts


@router.post("/predict/{event_id}", response_model=TrajectoryPrediction)
async def predict_for_event(
    event_id: UUID,
    wind_u: float = 4.0,
    wind_v: float = 1.5,
    current_u: float = 0.15,
    current_v: float = 0.08,
) -> TrajectoryPrediction:
    """Run trajectory prediction for a known event ID.

    Looks up the event location and runs the Lagrangian model with the
    provided wind and current parameters.

    Raises:
        HTTPException: 404 if the event is not found.
    """
    event = next(
        (e for e in app_state["events"] if e.id == event_id), None
    )
    if event is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found.")

    req = TrajectoryRequest(
        lon=event.location["lon"],
        lat=event.location["lat"],
        wind_u=wind_u,
        wind_v=wind_v,
        current_u=current_u,
        current_v=current_v,
    )
    prediction = await predict_trajectory(req)
    prediction.event_id = event_id
    return prediction
