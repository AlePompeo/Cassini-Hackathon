"""Kinéis platform webhook receiver.

The Kinéis cloud platform forwards uplink messages from buoys to this
endpoint via HTTP POST. Configure the callback URL in the Kinéis developer
portal:
    https://manager.kineis.com → Devices → Callbacks → Add HTTP endpoint

Expected POST body (application/json):
    {
        "deviceId":   "KIN0000001",
        "timestamp":  "2024-03-15T10:30:00.000Z",
        "payload":    "01...<48 hex chars>...",
        "satelliteId": "LEO-01",
        "rssi":        -85.5,
        "doppler_lat": 43.2,
        "doppler_lon": 14.5
    }

The 'payload' field contains the 48-hex-char (24-byte) packet encoded
by the buoy firmware. All other fields are optional metadata.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from exceptions import AquaGuardError
from iot.decoder import PacketDecodeError, decode_packet
from models.buoy import BuoyTelemetry
from state import app_state

router = APIRouter(prefix="/api/iot", tags=["iot"])


class KineisWebhookPayload(BaseModel):
    """Schema for Kinéis platform uplink callback."""

    deviceId:    str = ""
    timestamp:   str = ""
    payload:     str = Field(..., description="48-char hex uplink data")
    satelliteId: str = ""
    rssi:        float = 0.0
    doppler_lat: float | None = None
    doppler_lon: float | None = None


@router.post("/kineis/uplink", status_code=200)
async def kineis_uplink(body: KineisWebhookPayload) -> dict:
    """Receive a Kinéis uplink callback and store the decoded telemetry.

    Called by the Kinéis cloud platform whenever a satellite receives a
    transmission from one of the registered buoys.

    Returns 200 OK so the Kinéis platform does not retry.
    Returns 422 on payload validation errors so issues are visible in logs.
    """
    try:
        telemetry: BuoyTelemetry = decode_packet(
            hex_payload      = body.payload,
            kineis_device_id = body.deviceId,
            satellite_id     = body.satelliteId,
        )
    except PacketDecodeError as exc:
        # Log and reject — return 422 so Kinéis logs the failure
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Store in in-memory buoy telemetry list
    app_state["buoy_telemetry"].append(telemetry)

    # Keep only the last 500 readings to bound memory usage
    if len(app_state["buoy_telemetry"]) > 500:
        app_state["buoy_telemetry"] = app_state["buoy_telemetry"][-500:]

    # Update per-buoy latest reading index
    app_state["buoy_latest"][telemetry.buoy_id] = telemetry

    _log_receipt(telemetry)
    return {"status": "ok", "buoy_id": telemetry.buoy_id, "seq": telemetry.seq_num}


def _log_receipt(t: BuoyTelemetry) -> None:
    alerts_str = ", ".join(a.value for a in t.alerts) if t.alerts else "none"
    print(
        f"[IoT] Buoy {t.buoy_id} seq={t.seq_num} "
        f"pos=({t.latitude:.4f},{t.longitude:.4f}) "
        f"bat={t.power.bat_mv} mV "
        f"oil={t.water.oil_raw} uv={t.water.uv_raw} "
        f"alerts=[{alerts_str}]"
    )
