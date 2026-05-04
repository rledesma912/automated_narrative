"""Tests para SynopsisBeatMapper.map_one() (Spec-038/041, criterios B1/B2/B8/B9)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services import PromptBuilder
from src.application.use_cases.synopsis_beat_mapper import SynopsisBeatMapper
from src.domain.models import MacroBeat, NarrativeAnchors, Scenario, Story


def _make_story(**kwargs):
    story_id = uuid.uuid4()
    defaults = dict(
        id=story_id,
        title="El Monte Prohibido",
        protagonista="Irene, Ricardo",
        relator="Irene",
        sinopsis=(
            "La familia llega temprano a la casa de María. "
            "La abuela advierte sobre el Monte de los Espinillos. "
            "La fiesta se extiende y regresan de noche. "
            "Entran al monte bajo la tormenta. "
            "Ven la figura de María inmóvil en el claro."
        ),
        atmosfera="terror paranormal",
        scenarios=[
            Scenario(story_id=story_id, order_index=0, name="La casa de campo de la abuela María"),
            Scenario(
                story_id=story_id, order_index=1, name="La casa de campo donde ocurre la fiesta"
            ),
            Scenario(story_id=story_id, order_index=2, name="Monte siniestro y prohibido"),
        ],
    )
    defaults.update(kwargs)
    return Story(**defaults)


_ACTIVE_SCENARIO = "La casa de campo de la abuela María"

_ANCHORS = NarrativeAnchors(
    story_id=uuid.uuid4(),
    resonance_hamartia="Irene llega tranquila, sin sospechar nada.",
    resonance_hybris="Una presencia que imita a los conocidos.",
    resonance_anagnorisis="La figura de María inmóvil en el claro.",
    resonance_peripeteia="Monte de los Espinillos: espinillos, barro, relámpagos.",
    resonance_residual="Irene ya no puede cerrar los ojos sin ver el claro.",
)


def _beat_anchors(beat_id: int) -> dict:
    from unittest.mock import MagicMock

    from src.application.services.story_analyst_service import StoryAnalystService

    analyst = StoryAnalystService(MagicMock(), PromptBuilder())
    return analyst.resolve_beat_anchors(_ANCHORS, beat_id)


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
        result = await mapper.map_one(
            _make_story(), 1, _beat_anchors(1), active_scenario_description=_ACTIVE_SCENARIO
        )
        assert isinstance(result, MacroBeat)

    @pytest.mark.asyncio
    async def test_beat_number_matches(self):
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        result = await mapper.map_one(
            _make_story(), 2, _beat_anchors(2), active_scenario_description=_ACTIVE_SCENARIO
        )
        assert result.number == 2

    @pytest.mark.asyncio
    async def test_summary_not_empty(self):
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        result = await mapper.map_one(
            _make_story(), 1, _beat_anchors(1), active_scenario_description=_ACTIVE_SCENARIO
        )
        assert result.summary != ""


class TestMapOnePromptContent:
    """B1 — el prompt incluye ID del acto, anclajes y snapshot anterior."""

    @pytest.mark.asyncio
    async def test_prompt_contains_beat_id(self):
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        await mapper.map_one(
            _make_story(), 3, _beat_anchors(3), active_scenario_description=_ACTIVE_SCENARIO
        )
        prompt = llm.generate.call_args.kwargs["prompt"]
        assert "3" in prompt
        assert "climax" in prompt.lower() or "clim" in prompt.lower()

    @pytest.mark.asyncio
    async def test_prompt_contains_resonance_value(self):
        """B1 — prompt contiene el valor de resonancia del pilar."""
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        anchors = _beat_anchors(1)
        await mapper.map_one(
            _make_story(), 1, anchors, active_scenario_description=_ACTIVE_SCENARIO
        )
        prompt = llm.generate.call_args.kwargs["prompt"]
        assert anchors["resonance"] in prompt

    @pytest.mark.asyncio
    async def test_prompt_does_not_crash_without_contexto(self):
        """B1 — el prompt se genera sin error aunque no haya contexto (Spec-081)."""
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        anchors = _beat_anchors(1)
        # No debe lanzar excepción
        await mapper.map_one(
            _make_story(), 1, anchors, active_scenario_description=_ACTIVE_SCENARIO
        )
        prompt = llm.generate.call_args.kwargs["prompt"]
        assert len(prompt) > 0

    @pytest.mark.asyncio
    async def test_prompt_contains_prev_snapshot(self):
        """B1 — prompt incluye memory_snapshot del acto anterior cuando se pasa."""
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        snapshot = '{"last_events": "La familia llegó al campo.", "unresolved_mysteries": ""}'
        await mapper.map_one(
            _make_story(),
            2,
            _beat_anchors(2),
            prev_snapshot=snapshot,
            active_scenario_description=_ACTIVE_SCENARIO,
        )
        prompt = llm.generate.call_args.kwargs["prompt"]
        assert snapshot in prompt


class TestMapOneBeat1NoPrevMemory:
    """B2 — el prompt para el acto 1 NO incluye sección de memoria anterior."""

    @pytest.mark.asyncio
    async def test_beat1_has_no_prev_memory_section(self):
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        await mapper.map_one(
            _make_story(),
            1,
            _beat_anchors(1),
            prev_snapshot=None,
            active_scenario_description=_ACTIVE_SCENARIO,
        )
        prompt = llm.generate.call_args.kwargs["prompt"]
        assert "MEMORIA DEL ACTO ANTERIOR" not in prompt

    @pytest.mark.asyncio
    async def test_beat2_has_prev_memory_section_when_provided(self):
        """Contraste: beat 2 SÍ incluye memoria si se pasa snapshot."""
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        snapshot = '{"last_events": "Llegaron al campo."}'
        await mapper.map_one(
            _make_story(),
            2,
            _beat_anchors(2),
            prev_snapshot=snapshot,
            active_scenario_description=_ACTIVE_SCENARIO,
        )
        prompt = llm.generate.call_args.kwargs["prompt"]
        assert "MEMORIA DEL ACTO ANTERIOR" in prompt


class TestMapOneActiveScenarioInPrompt:
    """B8 — el prompt incluye el escenario activo designado por el resolver."""

    @pytest.mark.asyncio
    async def test_prompt_contains_active_scenario(self):
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        await mapper.map_one(
            _make_story(), 1, _beat_anchors(1), active_scenario_description=_ACTIVE_SCENARIO
        )
        prompt = llm.generate.call_args.kwargs["prompt"]
        assert _ACTIVE_SCENARIO in prompt

    @pytest.mark.asyncio
    async def test_prompt_contains_scenario_in_context_section(self):
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        await mapper.map_one(
            _make_story(), 1, _beat_anchors(1), active_scenario_description="Monte siniestro"
        )
        prompt = llm.generate.call_args.kwargs["prompt"]
        assert "Monte siniestro" in prompt


class TestMapOneActiveScenario:
    """B9 — active_scenario_id queda populado tras map_one()."""

    @pytest.mark.asyncio
    async def test_active_scenario_populated(self):
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        result = await mapper.map_one(
            _make_story(), 1, _beat_anchors(1), active_scenario_description=_ACTIVE_SCENARIO
        )
        assert result.active_scenario_id is not None
        assert result.active_scenario_id != ""

    @pytest.mark.asyncio
    async def test_active_scenario_from_llm_response(self):
        """El escenario extraído de la respuesta LLM toma precedencia."""
        llm = _make_llm(_MAP_ONE_RESPONSE)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        result = await mapper.map_one(
            _make_story(), 1, _beat_anchors(1), active_scenario_description=_ACTIVE_SCENARIO
        )
        assert "casa" in result.active_scenario_id.lower()

    @pytest.mark.asyncio
    async def test_fallback_scenario_when_llm_omits_escenario(self):
        """Fallback: si el LLM no incluye ESCENARIO:, se usa active_scenario_description."""
        no_scenario_response = "EVENTOS:\n- La familia llegó.\n- La abuela advirtió."
        llm = _make_llm(no_scenario_response)
        mapper = SynopsisBeatMapper(llm, PromptBuilder())
        result = await mapper.map_one(
            _make_story(),
            1,
            _beat_anchors(1),
            active_scenario_description=_ACTIVE_SCENARIO,
        )
        assert result.active_scenario_id == _ACTIVE_SCENARIO


class TestParseMapOneResponseRobustness:
    """Regresión: bugs detectados en debug del pipeline real (2026-04-25)."""

    def _make_mapper(self):
        llm = _make_llm("")
        return SynopsisBeatMapper(llm, PromptBuilder())

    def test_typo_escenarion_reconocido(self):
        """El parser acepta ESCENARION: (N extra) como variante del header."""
        text = (
            "ESCENARION: Casa de la abuela María\n\n"
            "EVENTOS:\n"
            "- La familia llega temprano.\n"
            "- Irene nota algo extraño.\n"
        )
        mapper = self._make_mapper()
        summary, scenario = mapper.beat_parser.parse_map_one_response(text, 1, [])
        assert scenario == "Casa de la abuela María"
        assert "La familia llega temprano." in summary

    def test_segundo_bloque_escenario_no_contamina_eventos(self):
        """Cuando el LLM incluye un segundo bloque ESCENARIO:, el parser se detiene."""
        text = (
            "ESCENARIO: Casa de la abuela María\n\n"
            "EVENTOS:\n"
            "- La familia llega.\n"
            "- Irene percibe inquietud.\n\n"
            "ESCENARIO: Monte de los espinillos\n\n"
            "EVENTOS:\n"
            "- Un laberinto siniestro.\n"
            "- Apariciones en la oscuridad.\n"
        )
        mapper = self._make_mapper()
        summary, scenario = mapper.beat_parser.parse_map_one_response(text, 1, [])
        assert "laberinto" not in summary.lower()
        assert "monte" not in summary.lower()
        assert "La familia llega." in summary

    def test_segundo_bloque_escenarion_typo_tampoco_contamina(self):
        """Variante con ESCENARION: (typo) como segundo bloque — también se detiene."""
        text = (
            "ESCENARIO: Casa de la abuela María\n\n"
            "EVENTOS:\n"
            "- La familia llega.\n\n"
            "ESCENARION: Monte de los espinillos\n\n"
            "EVENTOS:\n"
            "- Apariciones en el monte.\n"
        )
        mapper = self._make_mapper()
        summary, _ = mapper.beat_parser.parse_map_one_response(text, 1, [])
        assert "Apariciones en el monte." not in summary

    def test_escenario_correcto_sin_contaminacion(self):
        """Happy path: respuesta limpia de un solo bloque — OK."""
        text = (
            "ESCENARIO: Casa de la abuela María\n\n"
            "EVENTOS:\n"
            "- La familia llega temprano.\n"
            "- Irene muestra preocupación.\n"
            "- Ricardo mantiene postura escéptica.\n"
        )
        mapper = self._make_mapper()
        summary, scenario = mapper.beat_parser.parse_map_one_response(text, 1, [])
        assert scenario == "Casa de la abuela María"
        assert summary.count("- ") == 0 or "La familia llega" in summary
