"""Package for use cases."""

from src.application.use_cases.create_story import CreateStoryUseCase
from src.application.use_cases.director_use_case import DirectorUseCase
from src.application.use_cases.export_story import ExportStoryUseCase
from src.application.use_cases.voz_batch_use_case import VozBatchUseCase
from src.application.use_cases.voz_use_case import VozUseCase

# Alias para backwards compatibility
CreateStoryPlanUseCase = DirectorUseCase
NarrateBeatUseCase = VozUseCase
NarrateBatchUseCase = VozBatchUseCase

__all__ = [
    "CreateStoryUseCase",
    "DirectorUseCase",
    "VozUseCase",
    "VozBatchUseCase",
    "ExportStoryUseCase",
    # Alias (backwards compatibility)
    "CreateStoryPlanUseCase",
    "NarrateBeatUseCase",
    "NarrateBatchUseCase",
]
