"""Tests para el pipeline secuencial de Slice 6 (Spec-038).

Cubre:
- MemoryJournalist.extract() → (snapshot_json, NarrativeJournal)
- VozUseCase.narrate() → (MacroBeat, float)
- DirectorUseCase.execute_full() loop secuencial 5 beats
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.services import PromptBuilder
from src.application.services.memory_journalist import MemoryJournalist
from src.application.use_cases.director_use_case import DirectorUseCase
from src.application.use_cases.voz_use_case import VozUseCase
from src.domain.models import MacroBeat, NarrativeAnchors, NarrativeJournal, Story
from src.infrastructure.adapters import MockLLMAdapter


def _make_story(**kw):
    defaults = dict(
        title="El Monte Prohibido",
        protagonista="Irene, Ricardo",
        relator="Irene",
        sinopsis="La familia llega al campo y entra al monte de noche.",
        atmosfera="terror paranormal",
        reglas=["Ricardo ignora lo sobrenatural."],
    )
    defaults.update(kw)
    return Story(**defaults)


def _make_anchors(story_id=None):
    return NarrativeAnchors(
        story_id=story_id or uuid.uuid4(),
        resonance_hamartia="Irene llega tranquila.",
        resonance_hybris="Una presencia imitadora.",
        resonance_anagnorisis="La figura inmóvil en el claro.",
        resonance_peripeteia="Monte: espinillos, barro, relámpagos.",
        resonance_residual="Irene ya no puede cerrar los ojos.",
    )


def _make_macro_beat(number=1, content="Prosa narrativa."):
    return MacroBeat(
        number=number,
        summary=f"Evento del acto {number}.",
        active_scenario_id="Monte de los Espinillos",
        status="completed" if content else "pending",
        content=content or "",
        narrative_context=f"ACTO {number}: contexto pre-baked.",
    )


# ── MemoryJournalist.extract() ────────────────────────────────────────────────


class TestMemoryJournalistExtract:
    """extract() retorna solo NarrativeJournal (Spec-222)."""

    @pytest.mark.asyncio
    async def test_returns_narrative_journal(self):
        llm = MagicMock()
        llm.generate = AsyncMock(
            return_value=MagicMock(
                text='{"last_events": "Llegaron al monte.", "unresolved_mysteries": "", "physical_emotional_state": "Asustados"}',
                elapsed_s=0.2,
            )
        )
        journalist = MemoryJournalist(llm, PromptBuilder())
        story = _make_story()
        beat = _make_macro_beat(1)

        journal = await journalist.extract(story, beat)

        assert isinstance(journal, NarrativeJournal)
        assert journal.last_events == "Llegaron al monte."
        assert journal.physical_emotional_state == "Asustados"

    @pytest.mark.asyncio
    async def test_journal_contains_all_fields(self):
        llm = MagicMock()
        llm.generate = AsyncMock(
            return_value=MagicMock(
                text='{"last_events": "La familia entró.", "unresolved_mysteries": "X", "physical_emotional_state": "Tensos"}',
                elapsed_s=0.2,
            )
        )
        journalist = MemoryJournalist(llm, PromptBuilder())
        story = _make_story()
        beat = _make_macro_beat(2)

        journal = await journalist.extract(story, beat)

        assert journal.last_events == "La familia entró."
        assert journal.unresolved_mysteries == "X"
        assert journal.physical_emotional_state == "Tensos"

    @pytest.mark.asyncio
    async def test_journal_empty_on_parse_error(self):
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=MagicMock(text="invalid json", elapsed_s=0.1))
        journalist = MemoryJournalist(llm, PromptBuilder())
        story = _make_story()
        beat = _make_macro_beat(3)

        journal = await journalist.extract(story, beat)

        assert isinstance(journal, NarrativeJournal)
        assert journal.last_events == ""


# ── VozUseCase.narrate() ─────────────────────────────────────────────────────


class TestVozUseCaseNarrate:
    """narrate() usa el narrative_context pre-baked del MacroBeat."""

    @pytest.mark.asyncio
    async def test_returns_macro_beat_and_elapsed(self):
        llm = MagicMock()
        llm.generate = AsyncMock(
            return_value=MagicMock(
                text="La familia avanzó lentamente por el monte.",
                elapsed_s=1.5,
            )
        )
        voz = VozUseCase(llm, prompt_builder=PromptBuilder())
        story = _make_story()
        beat = _make_macro_beat(1, content=None)
        beat.status = "pending"

        result_beat, elapsed = await voz.narrate(beat, story)

        assert isinstance(result_beat, MacroBeat)
        assert isinstance(elapsed, float)

    @pytest.mark.asyncio
    async def test_beat_content_populated(self):
        llm = MagicMock()
        llm.generate = AsyncMock(
            return_value=MagicMock(
                text="El viento susurraba entre los espinillos.",
                elapsed_s=1.2,
            )
        )
        voz = VozUseCase(llm, prompt_builder=PromptBuilder())
        story = _make_story()
        beat = _make_macro_beat(2, content=None)
        beat.status = "pending"

        result_beat, _ = await voz.narrate(beat, story)

        assert result_beat.content != ""
        assert result_beat.content is not None

    @pytest.mark.asyncio
    async def test_beat_status_completed(self):
        llm = MagicMock()
        llm.generate = AsyncMock(
            return_value=MagicMock(
                text="Prosa de ejemplo.",
                elapsed_s=0.8,
            )
        )
        voz = VozUseCase(llm, prompt_builder=PromptBuilder())
        story = _make_story()
        beat = _make_macro_beat(1, content=None)
        beat.status = "pending"

        result_beat, _ = await voz.narrate(beat, story)

        assert result_beat.status == "completed"

    @pytest.mark.asyncio
    async def test_uses_narrative_context_in_prompt(self):
        llm = MagicMock()
        llm.generate = AsyncMock(
            return_value=MagicMock(
                text="Texto de prueba.",
                elapsed_s=0.5,
            )
        )
        voz = VozUseCase(llm, prompt_builder=PromptBuilder())
        story = _make_story()
        beat = _make_macro_beat(1, content=None)
        beat.narrative_context = "ACTO 1: contenido específico único"
        beat.status = "pending"

        await voz.narrate(beat, story)

        call_kwargs = llm.generate.call_args.kwargs
        assert "ACTO 1: contenido específico único" in call_kwargs.get("prompt", "")


# ── DirectorUseCase.execute_full() loop ───────────────────────────────────────


class TestDirectorExecuteFullLoop:
    """execute_full() orquesta ANALYST + N×(MAPPER+NC+VOZ+JOURNAL)."""

    def _make_mocks(self, story):
        anchors = _make_anchors(story.id)
        journal = NarrativeJournal(
            last_events="algo", unresolved_mysteries="", physical_emotional_state=""
        )

        mock_analyst = MagicMock()
        mock_analyst.extract_anchors = AsyncMock(return_value=anchors)
        mock_analyst.resolve_beat_anchors = MagicMock(
            return_value={"principal": "Irene llega tranquila.", "contexto": "Monte"}
        )

        mock_mapper = MagicMock()
        mock_mapper.map_one = AsyncMock(
            side_effect=lambda **kw: MacroBeat(
                number=kw["macro_beat_id"],
                summary=f"Evento {kw['macro_beat_id']}",
                active_scenario_id="Monte",
                status="pending",
            )
        )

        mock_voz = MagicMock()
        mock_voz.narrate = AsyncMock(
            side_effect=lambda mb, _s: (
                MacroBeat(
                    number=mb.number,
                    summary=mb.summary,
                    active_scenario_id=mb.active_scenario_id,
                    content="Prosa.",
                    status="completed",
                    narrative_context=mb.narrative_context,
                ),
                1.0,
            )
        )

        mock_journalist = MagicMock()
        mock_journalist.extract = AsyncMock(return_value=journal)

        return mock_analyst, mock_mapper, mock_voz, mock_journalist, journal

    @pytest.mark.asyncio
    async def test_yields_one_tuple_per_beat(self):
        story = _make_story()
        mock_analyst, mock_mapper, mock_voz, mock_journalist, _ = self._make_mocks(story)

        director = DirectorUseCase(
            MockLLMAdapter(),
            PromptBuilder(),
            voz=mock_voz,
            journalist=mock_journalist,
        )
        num_beats = director.prompt_builder.num_beats

        with (
            patch(
                "src.application.services.story_analyst_service.StoryAnalystService",
                return_value=mock_analyst,
            ),
            patch(
                "src.application.use_cases.director_use_case.SynopsisBeatMapper",
                return_value=mock_mapper,
            ),
        ):
            results = [item async for item in director.execute_full(story)]

        assert len(results) == num_beats

    @pytest.mark.asyncio
    async def test_beats_numbered_sequentially(self):
        story = _make_story()
        mock_analyst, mock_mapper, mock_voz, mock_journalist, _ = self._make_mocks(story)

        director = DirectorUseCase(
            MockLLMAdapter(),
            PromptBuilder(),
            voz=mock_voz,
            journalist=mock_journalist,
        )

        with (
            patch(
                "src.application.services.story_analyst_service.StoryAnalystService",
                return_value=mock_analyst,
            ),
            patch(
                "src.application.use_cases.director_use_case.SynopsisBeatMapper",
                return_value=mock_mapper,
            ),
        ):
            results = [item async for item in director.execute_full(story)]

        numbers = [r[0].number for r in results]
        assert numbers == list(range(1, len(numbers) + 1))

    @pytest.mark.asyncio
    async def test_on_plan_ready_called_with_num_beats(self):
        story = _make_story()
        mock_analyst, mock_mapper, mock_voz, mock_journalist, _ = self._make_mocks(story)

        director = DirectorUseCase(
            MockLLMAdapter(),
            PromptBuilder(),
            voz=mock_voz,
            journalist=mock_journalist,
        )
        num_beats = director.prompt_builder.num_beats

        fired = []
        with (
            patch(
                "src.application.services.story_analyst_service.StoryAnalystService",
                return_value=mock_analyst,
            ),
            patch(
                "src.application.use_cases.director_use_case.SynopsisBeatMapper",
                return_value=mock_mapper,
            ),
        ):
            async for _ in director.execute_full(
                story, on_plan_ready=lambda n, _t: fired.append(n)
            ):
                pass

        assert len(fired) == 1
        assert fired[0] == num_beats

    @pytest.mark.asyncio
    async def test_active_scenario_description_passed_to_map_one(self):
        """El director pasa active_scenario_description a cada map_one() call."""
        story = _make_story()
        mock_analyst, mock_mapper, mock_voz, mock_journalist, _ = self._make_mocks(story)

        director = DirectorUseCase(
            MockLLMAdapter(),
            PromptBuilder(),
            voz=mock_voz,
            journalist=mock_journalist,
        )

        with (
            patch(
                "src.application.services.story_analyst_service.StoryAnalystService",
                return_value=mock_analyst,
            ),
            patch(
                "src.application.use_cases.director_use_case.SynopsisBeatMapper",
                return_value=mock_mapper,
            ),
        ):
            async for _ in director.execute_full(story):
                pass

        first_call = mock_mapper.map_one.call_args_list[0]
        assert "active_scenario_description" in first_call.kwargs
