"""Package for routers."""

from src.presentation.routers.beat_router import router as beat_router
from src.presentation.routers.narrative_router import router as narrative_router
from src.presentation.routers.story_router import router as story_router
from src.presentation.routers.stream_router import router as stream_router

__all__ = ["story_router", "beat_router", "narrative_router", "stream_router"]
