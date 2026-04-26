from .detection import router as detection_router
from .trajectory import router as trajectory_router
from .alerts import router as alerts_router
from .buoys import router as buoys_router
from .kineis_webhook import router as kineis_router

__all__ = [
    "detection_router",
    "trajectory_router",
    "alerts_router",
    "buoys_router",
    "kineis_router",
]
