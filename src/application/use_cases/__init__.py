"""Package for use cases."""

from src.application.use_cases.create_story import CreateStoryUseCase
from src.application.use_cases.director_use_case import DirectorUseCase
from src.application.use_cases.get_story import GetStoryByIdUseCase
from src.application.use_cases.list_beats import ListBeatsUseCase
from src.application.use_cases.list_stories import ListStoriesUseCase
from src.application.use_cases.synopsis_beat_mapper import SynopsisBeatMapper
from src.application.use_cases.update_beat import UpdateBeatUseCase
from src.application.use_cases.voz_use_case import VozUseCase

CreateStoryPlanUseCase = DirectorUseCase
NarrateBeatUseCase = VozUseCase

__all__ = [
    "CreateStoryUseCase",
    "DirectorUseCase",
    "GetStoryByIdUseCase",
    "ListBeatsUseCase",
    "ListStoriesUseCase",
    "SynopsisBeatMapper",
    "UpdateBeatUseCase",
    "VozUseCase",
    "CreateStoryPlanUseCase",
    "NarrateBeatUseCase",
]
