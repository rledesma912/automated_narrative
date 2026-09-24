"""Tests para RegenerateBeatVozUseCase (Spec-430)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.use_cases.regenerate_beat_voz_use_case import RegenerateBeatVozUseCase
from src.domain.exceptions import StoryNotFoundError
from src.domain.models import (
    BeatStatus,
    GeneratedNarrative,
    MacroBeat,
    NarrativeAnchors,
    NarrativeJournal,
    Story,
)

_STORY_ID = uuid.uuid4()

_ANCHORS = NarrativeAnchors(
    story_id=_STORY_ID,
    resonance_hamartia="La grieta.",
    resonance_hybris="La transgresión.",
    resonance_anagnorisis="La epifanía.",
    resonance_peripeteia="La claustrofobia.",
    resonance_residual="La mancha.",
)


def _make_beat(number: int, content: str = "prosa original") -> MacroBeat:
    return MacroBeat(
        number=number,
        summary=f"evento del beat {number}",
        generated_act=content,
        status=BeatStatus.COMPLETED,
        active_scenario_id="Escenario X",
    )


def _make_story(beats: list[MacroBeat]) -> Story:
    return Story(
        id=_STORY_ID,
        title="Historia de prueba",
        protagonista="Ana",
        relator="primera_persona",
        sinopsis="Sinopsis de prueba",
        genero="terror",
        beats=beats,
    )


@pytest.fixture
def deps():
    story_repo = AsyncMock()
    beat_repo = AsyncMock()
    narrative_use_case = AsyncMock()
    voz_use_case = AsyncMock()
    prompt_builder = MagicMock()
    prompt_builder.build_narrative_context.return_value = "narrative_context ensamblado"
    llm = MagicMock()
    return {
        "story_repo": story_repo,
        "beat_repo": beat_repo,
        "narrative_use_case": narrative_use_case,
        "voz_use_case": voz_use_case,
        "prompt_builder": prompt_builder,
        "llm": llm,
    }


@pytest.fixture
def use_case(deps):
    return RegenerateBeatVozUseCase(
        llm=deps["llm"],
        prompt_builder=deps["prompt_builder"],
        story_repo=deps["story_repo"],
        beat_repo=deps["beat_repo"],
        narrative_use_case=deps["narrative_use_case"],
        voz_use_case=deps["voz_use_case"],
    )


@pytest.mark.asyncio
async def test_raises_when_story_not_found(use_case, deps):
    deps["story_repo"].get_by_id.return_value = None

    with pytest.raises(StoryNotFoundError):
        await use_case.execute(_STORY_ID, 1, uuid.uuid4())


@pytest.mark.asyncio
async def test_raises_when_beat_not_found(use_case, deps):
    deps["story_repo"].get_by_id.return_value = _make_story([_make_beat(1)])

    with pytest.raises(ValueError, match="no encontrado o no narrado"):
        await use_case.execute(_STORY_ID, 3, uuid.uuid4())


@pytest.mark.asyncio
async def test_raises_when_beat_has_no_content(use_case, deps):
    unnarrated = MacroBeat(number=2, summary="evento", generated_act="", status=BeatStatus.PENDING)
    deps["story_repo"].get_by_id.return_value = _make_story([_make_beat(1), unnarrated])

    with pytest.raises(ValueError, match="no encontrado o no narrado"):
        await use_case.execute(_STORY_ID, 2, uuid.uuid4())


@pytest.mark.asyncio
async def test_raises_when_no_anchors_persisted(use_case, deps):
    deps["story_repo"].get_by_id.return_value = _make_story([_make_beat(1)])
    deps["story_repo"].get_narrative_anchors.return_value = None

    with pytest.raises(ValueError, match="anclajes narrativos"):
        await use_case.execute(_STORY_ID, 1, uuid.uuid4())


@pytest.mark.asyncio
async def test_beat_1_no_busca_journal_previo(use_case, deps):
    deps["story_repo"].get_by_id.return_value = _make_story([_make_beat(1)])
    deps["story_repo"].get_narrative_anchors.return_value = _ANCHORS
    deps["voz_use_case"].narrate.return_value = (_make_beat(1, "prosa nueva"), 1.2)
    deps["narrative_use_case"].update_content.return_value = GeneratedNarrative(
        story_template_id=_STORY_ID, title="v1", content="contenido nuevo"
    )

    await use_case.execute(_STORY_ID, 1, uuid.uuid4())

    deps["story_repo"].get_journal.assert_not_called()


@pytest.mark.asyncio
async def test_beat_mayor_a_1_busca_journal_del_beat_anterior(use_case, deps):
    deps["story_repo"].get_by_id.return_value = _make_story([_make_beat(1), _make_beat(2)])
    deps["story_repo"].get_narrative_anchors.return_value = _ANCHORS
    deps["story_repo"].get_journal.return_value = NarrativeJournal(last_events="algo pasó")
    deps["voz_use_case"].narrate.return_value = (_make_beat(2, "prosa nueva"), 1.2)
    deps["narrative_use_case"].update_content.return_value = GeneratedNarrative(
        story_template_id=_STORY_ID, title="v1", content="contenido nuevo"
    )

    await use_case.execute(_STORY_ID, 2, uuid.uuid4())

    deps["story_repo"].get_journal.assert_awaited_once_with(_STORY_ID, 1)


@pytest.mark.asyncio
async def test_no_llama_al_journalist_ni_al_mapper(use_case, deps):
    """Spec-430: la regeneración parcial es deliberadamente solo-Voz."""
    deps["story_repo"].get_by_id.return_value = _make_story([_make_beat(1)])
    deps["story_repo"].get_narrative_anchors.return_value = _ANCHORS
    deps["voz_use_case"].narrate.return_value = (_make_beat(1, "prosa nueva"), 1.2)
    deps["narrative_use_case"].update_content.return_value = GeneratedNarrative(
        story_template_id=_STORY_ID, title="v1", content="contenido nuevo"
    )

    await use_case.execute(_STORY_ID, 1, uuid.uuid4())

    deps["voz_use_case"].narrate.assert_awaited_once()
    deps["story_repo"].save_journal.assert_not_called()


@pytest.mark.asyncio
async def test_persiste_el_beat_actualizado_y_reconsolida_la_variante(use_case, deps):
    narrative_id = uuid.uuid4()
    deps["story_repo"].get_by_id.return_value = _make_story([_make_beat(1), _make_beat(2)])
    deps["story_repo"].get_narrative_anchors.return_value = _ANCHORS
    regenerated_beat = _make_beat(2, "prosa REGENERADA")
    deps["voz_use_case"].narrate.return_value = (regenerated_beat, 1.2)
    expected_narrative = GeneratedNarrative(
        story_template_id=_STORY_ID, title="v1", content="contenido con prosa REGENERADA"
    )
    deps["narrative_use_case"].update_content.return_value = expected_narrative

    beat, narrative = await use_case.execute(_STORY_ID, 2, narrative_id)

    deps["beat_repo"].update.assert_awaited_once_with(regenerated_beat, _STORY_ID)
    deps["narrative_use_case"].update_content.assert_awaited_once()
    call_args = deps["narrative_use_case"].update_content.await_args
    assert call_args.args[0] == narrative_id
    updated_story = call_args.args[1]
    assert updated_story.beats[1].generated_act == "prosa REGENERADA"
    assert updated_story.beats[0].generated_act == "prosa original"
    assert narrative == expected_narrative
    assert beat == regenerated_beat
