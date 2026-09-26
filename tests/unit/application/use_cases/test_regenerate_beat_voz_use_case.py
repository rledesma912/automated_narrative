"""Tests para RegenerateBeatVozUseCase (Spec-430; Spec-530 S7: sale de la escaleta)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.prompt_builder import PromptBuilder
from src.application.use_cases.regenerate_beat_voz_use_case import RegenerateBeatVozUseCase
from src.domain.exceptions import StoryNotFoundError
from src.domain.models import (
    ActOutline,
    BeatStatus,
    GeneratedNarrative,
    MacroBeat,
    NarrativeJournal,
    Story,
)

_STORY_ID = uuid.uuid4()


def _make_beat(number: int, content: str = "prosa original") -> MacroBeat:
    return MacroBeat(
        number=number,
        summary=f"evento del beat {number}",
        generated_act=content,
        status=BeatStatus.COMPLETED,
    )


def _make_story(beats: list[MacroBeat], outline: bool = True) -> Story:
    return Story(
        id=_STORY_ID,
        title="Historia de prueba",
        protagonista="Ana",
        relator="primera_persona",
        sinopsis="Sinopsis de prueba",
        narrator_config={"storyteller_name": "Ana"},
        personajes_full=[{"name": "Ana", "role": "Narradora"}],
        beats=beats,
        outline=[ActOutline(number=n, events=[f"Hecho del acto {n}"]) for n in range(1, 6)]
        if outline
        else [],
    )


@pytest.fixture
def deps():
    voz = AsyncMock()
    return {
        "story_repo": AsyncMock(),
        "beat_repo": AsyncMock(),
        "narrative_use_case": AsyncMock(),
        "voz_use_case": voz,
        "llm": MagicMock(),
    }


@pytest.fixture
def use_case(deps):
    return RegenerateBeatVozUseCase(
        llm=deps["llm"],
        prompt_builder=PromptBuilder(),
        story_repo=deps["story_repo"],
        beat_repo=deps["beat_repo"],
        narrative_use_case=deps["narrative_use_case"],
        voz_use_case=deps["voz_use_case"],
    )


async def test_raises_when_story_not_found(use_case, deps):
    deps["story_repo"].get_by_id.return_value = None
    with pytest.raises(StoryNotFoundError):
        await use_case.execute(_STORY_ID, 1, uuid.uuid4())


@pytest.mark.parametrize("beats", [[], [_make_beat(1, "")]])
async def test_raises_when_beat_not_found_or_empty(use_case, deps, beats):
    deps["story_repo"].get_by_id.return_value = _make_story(beats)
    with pytest.raises(ValueError, match="no encontrado o no narrado"):
        await use_case.execute(_STORY_ID, 1, uuid.uuid4())


async def test_sin_escaleta_pide_regenerar_entera(use_case, deps):
    deps["story_repo"].get_by_id.return_value = _make_story([_make_beat(1)], outline=False)
    with pytest.raises(ValueError, match="no tiene escaleta"):
        await use_case.execute(_STORY_ID, 1, uuid.uuid4())


async def test_acto_1_sin_memoria_previa(use_case, deps):
    deps["story_repo"].get_by_id.return_value = _make_story([_make_beat(1)])
    deps["voz_use_case"].narrate_with_prompts.return_value = (_make_beat(1, "nueva"), 1.0)

    await use_case.execute(_STORY_ID, 1, uuid.uuid4())

    deps["story_repo"].get_journal.assert_not_called()
    _, system, user = deps["voz_use_case"].narrate_with_prompts.await_args.args
    assert "Sos Ana" in system
    assert "- Hecho del acto 1" in user and "(es el comienzo del relato)" in user


async def test_acto_mayor_a_1_usa_la_memoria_del_acto_anterior(use_case, deps):
    deps["story_repo"].get_by_id.return_value = _make_story([_make_beat(1), _make_beat(2)])
    deps["story_repo"].get_journal.return_value = NarrativeJournal(
        last_events="Acto 1: Ana llega.", used_motifs=["el reloj detenido"]
    )
    deps["voz_use_case"].narrate_with_prompts.return_value = (_make_beat(2, "nueva"), 1.0)

    await use_case.execute(_STORY_ID, 2, uuid.uuid4())

    deps["story_repo"].get_journal.assert_awaited_once_with(_STORY_ID, 1)
    _, _, user = deps["voz_use_case"].narrate_with_prompts.await_args.args
    assert "Acto 1: Ana llega." in user and "- el reloj detenido" in user
    deps["story_repo"].save_journal.assert_not_called()  # no toca la memoria


async def test_persiste_el_beat_actualizado_y_reconsolida_la_variante(use_case, deps):
    narrative_id = uuid.uuid4()
    deps["story_repo"].get_by_id.return_value = _make_story([_make_beat(1), _make_beat(2)])
    deps["story_repo"].get_journal.return_value = None
    regenerated = _make_beat(2, "prosa REGENERADA")
    deps["voz_use_case"].narrate_with_prompts.return_value = (regenerated, 1.2)
    expected = GeneratedNarrative(story_template_id=_STORY_ID, title="v1", content="x")
    deps["narrative_use_case"].update_content.return_value = expected

    beat, narrative = await use_case.execute(_STORY_ID, 2, narrative_id)

    deps["beat_repo"].update.assert_awaited_once_with(regenerated, _STORY_ID)
    updated_story = deps["narrative_use_case"].update_content.await_args.args[1]
    assert [b.generated_act for b in updated_story.beats] == ["prosa original", "prosa REGENERADA"]
    assert (beat, narrative) == (regenerated, expected)
