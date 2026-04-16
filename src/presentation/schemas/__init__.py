"""Package for schemas."""

from src.presentation.schemas.request import BeatUpdateRequest, StoryCreateRequest
from src.presentation.schemas.response import BeatResponse, StoryResponse

__all__ = [
    "StoryCreateRequest",
    "BeatUpdateRequest",
    "StoryResponse",
    "BeatResponse",
]
