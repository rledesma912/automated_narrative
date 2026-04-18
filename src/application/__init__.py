"""Application layer - Use cases and services."""

from src.application.dto import BeatCreateDTO, BeatResponseDTO, StoryCreateDTO, StoryResponseDTO
from src.application.services import MemoryJournalist, PromptBuilder
from src.application.use_cases import (
    CreateStoryUseCase,
    DirectorUseCase,
    ExportStoryUseCase,
    VozBatchUseCase,
    VozUseCase,
)

# Alias para backwards compatibility
CreateStoryPlanUseCase = DirectorUseCase
NarrateBatchUseCase = VozBatchUseCase
NarrateBeatUseCase = VozUseCase

__all__ = [
    "StoryCreateDTO",
    "StoryResponseDTO",
    "BeatCreateDTO",
    "BeatResponseDTO",
    "CreateStoryUseCase",
    "DirectorUseCase",
    "VozUseCase",
    "VozBatchUseCase",
    "ExportStoryUseCase",
    "PromptBuilder",
    "MemoryJournalist",
    # Alias (backwards compatibility)
    "CreateStoryPlanUseCase",
    "NarrateBeatUseCase",
    "NarrateBatchUseCase",
]
