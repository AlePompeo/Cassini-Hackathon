"""Detection API endpoints — pollution event search and retrieval."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from models.pollution_event import BoundingBox, PollutionEvent, PollutionType, Severity
from processing.sentinel2 import detect_pollution, classify_pollution
from services.copernicus import CopernicusClient
from state import app_state

router = APIRouter(prefix="/api/detection", tags=["detection"])


class AnalyzeRequest(BaseModel):
    """Body for POST /api/detection/analyze."""

    aoi: BoundingBox
    start_date: datetime
    end_date: datetime
    satellite: str = "Sentinel-2"


@router.post("/analyze", response_model=list[PollutionEvent])
async def analyze_area(body: AnalyzeRequest) -> list[PollutionEvent]:
    """Trigger satellite analysis over an area of interest.

    Fetches available Sentinel scenes from Copernicus Dataspace, applies
    the MCI/VNRI/SAR pipeline, and returns detected pollution events.

    For the demo, synthetic data is returned immediately.
    """
    client = CopernicusClient()

    if "Sentinel-2" in body.satellite:
        scenes = client.search_sentinel2(
            aoi=body.aoi,
            start_date=body.start_date,
            end_date=body.end_date,
        )
        if not scenes:
            return []

        bands = client.get_sample_sentinel2_bands(scenes[0]["id"])
        indices = detect_pollution(bands)
        labels = classify_pollution(
            mci=indices["mci"],
            vnri=indices["vnri"],
            osi=indices["osi"],
        )
        # For demo: return cached events filtered to AOI
        events = [
            e for e in app_state["events"]
            if (body.aoi.min_lon <= e.location["lon"] <= body.aoi.max_lon
                and body.aoi.min_lat <= e.location["lat"] <= body.aoi.max_lat)
        ]
        return events[:10]

    return app_state["events"][:5]


@router.get("/events", response_model=list[PollutionEvent])
async def list_events(
    event_type: PollutionType | None = Query(None),
    severity: Severity | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[PollutionEvent]:
    """Return the most recent pollution events, optionally filtered.

    Args:
        event_type: Filter by pollution type.
        severity: Filter by minimum severity.
        limit: Maximum number of events to return.
    """
    events: list[PollutionEvent] = app_state["events"]

    severity_order = {
        Severity.LOW: 0,
        Severity.MEDIUM: 1,
        Severity.HIGH: 2,
        Severity.CRITICAL: 3,
    }

    if event_type:
        events = [e for e in events if e.event_type == event_type]
    if severity:
        min_level = severity_order[severity]
        events = [e for e in events if severity_order[e.severity] >= min_level]

    return events[:limit]


@router.get("/events/{event_id}", response_model=PollutionEvent)
async def get_event(event_id: UUID) -> PollutionEvent:
    """Return a single pollution event by ID.

    Args:
        event_id: UUID of the pollution event.

    Raises:
        HTTPException: 404 if the event is not found.
    """
    for event in app_state["events"]:
        if event.id == event_id:
            return event
    raise HTTPException(status_code=404, detail=f"Event {event_id} not found.")
