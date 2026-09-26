"""DirectorUseCase (Spec-530 S7): un solo camino, el relato sale de la escaleta."""

from unittest.mock import AsyncMock

from src.application.services.prompt_builder import PromptBuilder
from src.application.use_cases.director_use_case import DirectorUseCase
from src.domain.jobs import JobStage
from src.domain.models import ActOutline, Story
from src.infrastructure.adapters import MockLLMAdapter


class RecordingMock(MockLLMAdapter):
    def __init__(self):
        super().__init__()
        self.roles: list[str] = []

    async def generate(self, prompt, *, role=None, **kwargs):
        self.roles.append(role)
        return await super().generate(prompt, role=role, **kwargs)


def _story(outline: bool) -> Story:
    return Story(
        title="Prueba",
        protagonista="Ana",
        relator="Primera persona",
        sinopsis="Ana cruza el monte de noche.",
        narrator_config={"storyteller_name": "Ana"},
        personajes_full=[{"name": "Ana", "role": "Narradora"}],
        outline=[ActOutline(number=n, events=[f"Hecho {n}"]) for n in range(1, 6)]
        if outline
        else [],
    )


async def _run(director: DirectorUseCase, story: Story) -> tuple[list, list]:
    stages: list = []
    beats = [
        b
        async for b, _j, _t in director.execute_full(
            story, on_stage=lambda s, n: stages.append((s, n))
        )
    ]
    return beats, stages


async def test_con_escaleta_solo_voz_y_memoria():
    llm = RecordingMock()
    beats, stages = await _run(DirectorUseCase(llm, PromptBuilder()), _story(outline=True))

    assert [b.number for b in beats] == [1, 2, 3, 4, 5]
    assert llm.roles == ["voz", "journal"] * 5
    assert beats[0].summary == "- Hecho 1"
    assert stages[:2] == [(JobStage.VOZ, 1), (JobStage.JOURNAL, 1)]


async def test_sin_escaleta_primero_la_arma_y_la_guarda():
    llm = RecordingMock()
    repo = AsyncMock()
    story = _story(outline=False)

    beats, stages = await _run(DirectorUseCase(llm, PromptBuilder(), story_repo=repo), story)

    assert llm.roles[:2] == ["planificador", "verificador"]
    assert llm.roles[2:] == ["voz", "journal"] * 5
    assert stages[:2] == [(JobStage.PLANIFICADOR, None), (JobStage.VERIFICADOR, None)]
    assert len(story.outline) == 5 and len(beats) == 5
    repo.save_outline.assert_awaited_once_with(story.id, story.outline)
