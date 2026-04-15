"""Package for schemas."""

from src.presentation.schemas.request import StoryCreateRequest, BeatUpdateRequest
from src.presentation.schemas.response import StoryResponse, BeatResponse

__all__ = [
    "StoryCreateRequest",
    "BeatUpdateRequest",
    "StoryResponse",
    "BeatResponse",
]
