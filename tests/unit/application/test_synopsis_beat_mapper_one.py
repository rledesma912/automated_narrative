"""Tests para SynopsisBeatMapper.map_one() (Spec-038, criterios B1/B2/B8/B9)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services import PromptBuilder
from src.application.use_cases.synopsis_beat_mapper import SynopsisBeatMapper
from src.domain.models import MacroBeat, NarrativeAnchors, Story


def _make_story(**kwargs):
    defaults = dict(
        title="El Monte Prohibido",
        protagonista="Irene, Ricardo",
        relator="Irene",
        escenarios="La casa de la abuela / La fiesta / El monte",
        sinopsis=(
            "La familia llega temprano a la casa de María. "
            "La abuela advierte sobre el Monte de los Espinillos. "
            "La fiesta se extiende y regresan de noche. "
            "Entran al monte bajo la tormenta. "
            "Ven la figura de María inmóvil en el claro."
        ),
        atmosfera="terror paranormal",
    )
    defaults.update(kwargs)
    return Story(**defaults)


_CRONOLOGIC = [
    "La casa de campo de la abuela María",
    "La casa de campo donde ocurre la fiesta",
    "Monte siniestro y prohibido",
]

_ANCHORS = NarrativeAnchors(
    story_id=uuid.uuid4(),
    initial_state="Irene llega tranquila, sin sospechar nada.",
    threat_nature="Una presencia que imita a los conocidos.",
    horror_peak="La figura de María inmóvil en el claro.",
    spatial_anchor="Monte de los Espinillos: espinillos, barro, relámpagos.",
)


def _beat_anchors(beat_id: int) -> dict:
    from src.domain.models import resolve_beat_anchors
    builder = PromptBuilder()
    return resolve_beat_anchors(_ANCHORS, beat_id, builder._beats_spec)


def _make_llm(text: str):
    llm = AsyncMock()
    resp = MagicMock()
    resp.text = text
    resp.elapsed_s = 0.3
    llm.generate = AsyncMock(return_value=resp)
    return llm


_MAP_ONE_RESPONSE = (
    "ESCENARIO: La casa de campo de la abuela María\n\n"
    "EVENTOS:\n"
    "- La familia llega temprano a la casa de María.\n"
    "- La abuela advierte sobre el Monte de los Espinillos.\n"
)


class TestMapOneReturnValue:

    @pytest.mark.asyncio
    async def test_returns_macro_beat(self):
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        result = await mapper.map_one(_make_story(), 1, _beat_anchors(1), cronologic_scenarios=_CRONOLOGIC)
        assert isinstance(result, MacroBeat)

    @pytest.mark.asyncio
    async def test_beat_number_matches(self):
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        result = await mapper.map_one(_make_story(), 2, _beat_anchors(2), cronologic_scenarios=_CRONOLOGIC)
        assert result.number == 2

    @pytest.mark.asyncio
    async def test_summary_not_empty(self):
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        result = await mapper.map_one(_make_story(), 1, _beat_anchors(1), cronologic_scenarios=_CRONOLOGIC)
        assert result.summary != ""


class TestMapOnePromptContent:
    """B1 — el prompt incluye ID del acto, anclajes y snapshot anterior."""

    @pytest.mark.asyncio
    async def test_prompt_contains_beat_id(self):
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        await mapper.map_one(_make_story(), 3, _beat_anchors(3), cronologic_scenarios=_CRONOLOGIC)
        prompt = llm.generate.call_args.kwargs["prompt"]
        assert "3" in prompt
        assert "climax" in prompt.lower() or "clim" in prompt.lower()

    @pytest.mark.asyncio
    async def test_prompt_contains_anchor_principal(self):
        """B1 — prompt contiene el valor del anclaje principal."""
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        anchors = _beat_anchors(1)
        await mapper.map_one(_make_story(), 1, anchors, cronologic_scenarios=_CRONOLOGIC)
        prompt = llm.generate.call_args.kwargs["prompt"]
        assert anchors["principal"] in prompt

    @pytest.mark.asyncio
    async def test_prompt_contains_anchor_contexto(self):
        """B1 — prompt contiene el valor del anclaje de contexto."""
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        anchors = _beat_anchors(1)
        await mapper.map_one(_make_story(), 1, anchors, cronologic_scenarios=_CRONOLOGIC)
        prompt = llm.generate.call_args.kwargs["prompt"]
        assert anchors["contexto"] in prompt

    @pytest.mark.asyncio
    async def test_prompt_contains_prev_snapshot(self):
        """B1 — prompt incluye memory_snapshot del acto anterior cuando se pasa."""
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        snapshot = '{"last_events": "La familia llegó al campo.", "unresolved_mysteries": ""}'
        await mapper.map_one(_make_story(), 2, _beat_anchors(2), prev_snapshot=snapshot, cronologic_scenarios=_CRONOLOGIC)
        prompt = llm.generate.call_args.kwargs["prompt"]
        assert snapshot in prompt


class TestMapOneBeat1NoPrevMemory:
    """B2 — el prompt para el acto 1 NO incluye sección de memoria anterior."""

    @pytest.mark.asyncio
    async def test_beat1_has_no_prev_memory_section(self):
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        await mapper.map_one(_make_story(), 1, _beat_anchors(1), prev_snapshot=None, cronologic_scenarios=_CRONOLOGIC)
        prompt = llm.generate.call_args.kwargs["prompt"]
        assert "MEMORIA DEL ACTO ANTERIOR" not in prompt

    @pytest.mark.asyncio
    async def test_beat2_has_prev_memory_section_when_provided(self):
        """Contraste: beat 2 SÍ incluye memoria si se pasa snapshot."""
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        snapshot = '{"last_events": "Llegaron al campo."}'
        await mapper.map_one(_make_story(), 2, _beat_anchors(2), prev_snapshot=snapshot, cronologic_scenarios=_CRONOLOGIC)
        prompt = llm.generate.call_args.kwargs["prompt"]
        assert "MEMORIA DEL ACTO ANTERIOR" in prompt


class TestMapOneCronologicScenarios:
    """B8 — el prompt incluye cronologic_scenarios como lista."""

    @pytest.mark.asyncio
    async def test_prompt_contains_cronologic_list(self):
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        await mapper.map_one(_make_story(), 1, _beat_anchors(1), cronologic_scenarios=_CRONOLOGIC)
        prompt = llm.generate.call_args.kwargs["prompt"]
        for scenario in _CRONOLOGIC:
            assert scenario in prompt

    @pytest.mark.asyncio
    async def test_cronologic_list_is_formatted_as_bullets(self):
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        await mapper.map_one(_make_story(), 1, _beat_anchors(1), cronologic_scenarios=_CRONOLOGIC)
        prompt = llm.generate.call_args.kwargs["prompt"]
        assert "- La casa de campo de la abuela María" in prompt


class TestMapOneActiveScenario:
    """B9 — active_scenario_id queda populado tras map_one() con un valor de cronologic_scenarios."""

    @pytest.mark.asyncio
    async def test_active_scenario_populated(self):
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        result = await mapper.map_one(_make_story(), 1, _beat_anchors(1), cronologic_scenarios=_CRONOLOGIC)
        assert result.active_scenario_id is not None
        assert result.active_scenario_id != ""

    @pytest.mark.asyncio
    async def test_active_scenario_is_from_cronologic_list(self):
        """El escenario identificado pertenece (o se aproxima) a la lista de cronologic_scenarios."""
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        result = await mapper.map_one(_make_story(), 1, _beat_anchors(1), cronologic_scenarios=_CRONOLOGIC)
        # La respuesta mockeada dice "La casa de campo de la abuela María"
        assert "casa" in result.active_scenario_id.lower() or result.active_scenario_id in _CRONOLOGIC

    @pytest.mark.asyncio
    async def test_fallback_scenario_when_llm_omits_escenario(self):
        """Fallback: si el LLM no incluye ESCENARIO:, se usa posición proporcional."""
        no_scenario_response = "EVENTOS:\n- La familia llegó.\n- La abuela advirtió."
        llm = _make_llm(no_scenario_response)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        result = await mapper.map_one(_make_story(), 1, _beat_anchors(1), cronologic_scenarios=_CRONOLOGIC)
        # Fallback usa índice 0 (beat 1 → _CRONOLOGIC[0])
        assert result.active_scenario_id == _CRONOLOGIC[0]
