"""Test E2E — Slice 8 (Spec-038).

Verifica el pipeline completo con el_monte_prohibido.md:
- Parser → Story con cronologic_scenarios
- execute_full() ANALYST + 5×(MAPPER+NC+VOZ+JOURNAL) = 16 llamadas LLM
- Cada beat: content, narrative_context, memory_snapshot populados
- "caballo" presente en el contenido (correcto para este relato de campo)
- "auto" y "celular" ausentes (no son elementos del universo de la historia)
"""

import json
from pathlib import Path

import pytest

from src.application.services import PromptBuilder
from src.application.use_cases.director_use_case import DirectorUseCase
from src.domain.interfaces import LLMResponse
from src.domain.models import Story
from src.infrastructure.parsers.markdown_parser import MarkdownStoryParser

# ── Mock LLM con secuencia de respuestas ─────────────────────────────────────

_ANALYST_RESPONSE = json.dumps(
    {
        "initial_state": "Irene llega tranquila al campo, sin sospechar nada.",
        "threat_nature": "Una presencia que imita a los conocidos de la familia.",
        "horror_peak": "La figura de María inmóvil en el claro del monte.",
        "spatial_anchor": "Monte de los Espinillos: espinillos cerrados, barro, relámpagos.",
    },
    ensure_ascii=False,
)

_MAPPER_RESPONSES = [
    (
        "ESCENARIO: La casa de campo de la abuela María\n\n"
        "EVENTOS:\n"
        "- La familia llega temprano al campo con el caballo y los niños.\n"
        "- La abuela advierte: eviten el Monte de los Espinillos de noche."
    ),
    (
        "ESCENARIO: La casa de campo donde ocurre la fiesta\n\n"
        "EVENTOS:\n"
        "- La fiesta se extiende más de lo previsto hasta la noche.\n"
        "- Una tormenta comienza. El caballo se empaca ante los truenos."
    ),
    (
        "ESCENARIO: Monte siniestro y prohibido donde ocurre lo paranormal\n\n"
        "EVENTOS:\n"
        "- El caballo avanza con dificultad entre los espinillos cerrados.\n"
        "- Susurros y sombras inexplicables comienzan a rodearlos."
    ),
    (
        "ESCENARIO: Monte siniestro y prohibido donde ocurre lo paranormal\n\n"
        "EVENTOS:\n"
        "- En el claro del monte, la figura de María los espera inmóvil.\n"
        "- El miedo se vuelve absoluto. Irene comienza a rezar."
    ),
    (
        "ESCENARIO: Monte siniestro y prohibido donde ocurre lo paranormal\n\n"
        "EVENTOS:\n"
        "- La presión cede gradualmente. El caballo retoma el paso.\n"
        "- Salen del monte al amanecer, exhaustos pero ilesos."
    ),
]

_VOZ_RESPONSES = [
    "Llegamos temprano esa tarde al campo de María, con el caballo trotando suave por el camino de tierra. Los niños bajaron de un salto. Mientras tomábamos mates, la abuela nos miró fijo y dijo que si se hacía tarde, no volviéramos por el monte.",
    "La fiesta duró más de lo pensado. Cuando quisimos regresar, la noche había cerrado y el caballo ya sentía la tormenta que se venía. Los relámpagos iluminaban el camino en destellos fugaces.",
    "El monte nos tragó. El caballo resoplaba entre los espinillos, aplastado por la oscuridad. Los sonidos no eran del viento ni del agua. Algo se movía entre los arbustos sin pisada, sin peso.",
    "Y entonces la vimos. La madre de Ricardo. Inmóvil en el claro, mirándons. Imposible. Rezé sin parar, con los niños aferrados a mí.",
    "De a poco, sin que supiéramos exactamente cuándo, el monte nos soltó. El caballo caminó solo hacia la salida. Llegamos al amanecer. Nadie habló del claro. Pero todos lo recordamos.",
]

_JOURNAL_RESPONSE = json.dumps(
    {
        "last_events": "La familia transitó el monte a caballo bajo la tormenta.",
        "unresolved_mysteries": "La figura de María en el claro.",
        "physical_emotional_state": "Agotados y aterrados.",
    },
    ensure_ascii=False,
)


class _SequenceLLM:
    """LLM mock que despacha respuestas en orden: ANALYST → N×(MAPPER, VOZ, JOURNAL)."""

    def __init__(self, num_beats: int = 5):
        self._num_beats = num_beats
        self.call_count = 0
        self._build_sequence()

    def _build_sequence(self):
        seq = [_ANALYST_RESPONSE]
        for i in range(self._num_beats):
            seq.append(_MAPPER_RESPONSES[i % len(_MAPPER_RESPONSES)])
            seq.append(_VOZ_RESPONSES[i % len(_VOZ_RESPONSES)])
            seq.append(_JOURNAL_RESPONSE)
        self._sequence = seq

    async def generate(
        self, prompt, *, system_prompt=None, model="mock", temperature=0.6, role=None, **kwargs
    ):
        idx = self.call_count
        self.call_count += 1
        text = self._sequence[idx] if idx < len(self._sequence) else "Fallback."
        return LLMResponse(text=text, context=None)

    async def close(self):
        pass


# ── Fixture: Story desde el_monte_prohibido.md ───────────────────────────────


def _load_story() -> Story:
    input_dir = Path(__file__).parent.parent.parent / "input_stories"
    parser = MarkdownStoryParser(input_dir=input_dir)
    data = parser.parse("el_monte_prohibido.yaml")
    from src.domain.models import Scenario

    story = Story(
        title=data.title,
        protagonista=data.protagonista,
        relator=data.relator,
        sinopsis=data.sinopsis,
        atmosfera=data.atmosfera,
        reglas=data.reglas,
        storyteller_config=data.storyteller_config or None,
    )
    story.scenarios = [
        Scenario(story_id=story.id, order_index=i, name=name)
        for i, name in enumerate(data.cronologic_scenarios)
    ]
    return story


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestSlice8E2EMontePipeline:
    @pytest.fixture
    def story(self):
        return _load_story()

    @pytest.fixture
    def director(self):
        pb = PromptBuilder()
        llm = _SequenceLLM(num_beats=pb.num_beats)
        return DirectorUseCase(llm, pb), llm

    @pytest.mark.asyncio
    async def test_parser_extracts_story(self, story):
        assert "monte" in story.title.lower()
        assert "Irene" in story.protagonista
        assert story.sinopsis != ""
        assert story.atmosfera != ""

    @pytest.mark.asyncio
    async def test_parser_extracts_escenarios(self, story):
        scenario_names = [s.name for s in story.scenarios]
        assert any("monte" in n.lower() for n in scenario_names)

    @pytest.mark.asyncio
    async def test_pipeline_yields_all_beats(self, story):
        pb = PromptBuilder()
        llm = _SequenceLLM(num_beats=pb.num_beats)
        director = DirectorUseCase(llm, pb)

        results = [item async for item in director.execute_full(story)]
        assert len(results) == pb.num_beats

    @pytest.mark.asyncio
    async def test_all_beats_completed(self, story):
        pb = PromptBuilder()
        llm = _SequenceLLM(num_beats=pb.num_beats)
        director = DirectorUseCase(llm, pb)

        results = [item async for item in director.execute_full(story)]
        for beat, _, _ in results:
            assert beat.status == "completed"

    @pytest.mark.asyncio
    async def test_all_beats_have_content(self, story):
        pb = PromptBuilder()
        llm = _SequenceLLM(num_beats=pb.num_beats)
        director = DirectorUseCase(llm, pb)

        results = [item async for item in director.execute_full(story)]
        for beat, _, _ in results:
            assert beat.content != ""

    @pytest.mark.asyncio
    async def test_all_beats_have_narrative_context(self, story):
        pb = PromptBuilder()
        llm = _SequenceLLM(num_beats=pb.num_beats)
        director = DirectorUseCase(llm, pb)

        results = [item async for item in director.execute_full(story)]
        for beat, _, _ in results:
            assert beat.narrative_context is not None
            assert len(beat.narrative_context) > 10

    @pytest.mark.asyncio
    async def test_beats_numbered_1_to_5(self, story):
        pb = PromptBuilder()
        llm = _SequenceLLM(num_beats=pb.num_beats)
        director = DirectorUseCase(llm, pb)

        results = [item async for item in director.execute_full(story)]
        numbers = [b.number for b, _, _ in results]
        assert numbers == list(range(1, pb.num_beats + 1))

    @pytest.mark.asyncio
    async def test_caballo_present_in_content(self, story):
        """'caballo' aparece en el contenido narrado (correcto para un relato de campo)."""
        pb = PromptBuilder()
        llm = _SequenceLLM(num_beats=pb.num_beats)
        director = DirectorUseCase(llm, pb)

        results = [item async for item in director.execute_full(story)]
        all_content = " ".join(b.content for b, _, _ in results)
        assert "caballo" in all_content.lower()

    @pytest.mark.asyncio
    async def test_auto_absent_from_content(self, story):
        """'auto' no aparece (elemento ajeno al universo de la historia)."""
        pb = PromptBuilder()
        llm = _SequenceLLM(num_beats=pb.num_beats)
        director = DirectorUseCase(llm, pb)

        results = [item async for item in director.execute_full(story)]
        all_content = " ".join(b.content for b, _, _ in results)
        assert "auto" not in all_content.lower()

    @pytest.mark.asyncio
    async def test_celular_absent_from_content(self, story):
        """'celular' no aparece (elemento ajeno al universo de la historia)."""
        pb = PromptBuilder()
        llm = _SequenceLLM(num_beats=pb.num_beats)
        director = DirectorUseCase(llm, pb)

        results = [item async for item in director.execute_full(story)]
        all_content = " ".join(b.content for b, _, _ in results)
        assert "celular" not in all_content.lower()

    @pytest.mark.asyncio
    async def test_narrative_context_contains_no_full_synopsis(self, story):
        """El narrative_context no contiene la sinopsis completa (solo el evento del beat)."""
        pb = PromptBuilder()
        llm = _SequenceLLM(num_beats=pb.num_beats)
        director = DirectorUseCase(llm, pb)

        results = [item async for item in director.execute_full(story)]
        for beat, _, _ in results:
            # La sinopsis completa (250+ chars) no debería estar en el nc
            assert story.sinopsis not in (beat.narrative_context or "")

    @pytest.mark.asyncio
    async def test_active_scenario_populated_each_beat(self, story):
        pb = PromptBuilder()
        llm = _SequenceLLM(num_beats=pb.num_beats)
        director = DirectorUseCase(llm, pb)

        results = [item async for item in director.execute_full(story)]
        for beat, _, _ in results:
            assert beat.active_scenario_id is not None
            assert beat.active_scenario_id != ""

    @pytest.mark.asyncio
    async def test_journal_updated_each_beat(self, story):
        pb = PromptBuilder()
        llm = _SequenceLLM(num_beats=pb.num_beats)
        director = DirectorUseCase(llm, pb)

        results = [item async for item in director.execute_full(story)]
        for _, journal, _ in results:
            assert journal is not None

    @pytest.mark.asyncio
    async def test_total_llm_calls(self, story):
        """Pipeline realiza exactamente 1 + num_beats×3 llamadas LLM."""
        pb = PromptBuilder()
        llm = _SequenceLLM(num_beats=pb.num_beats)
        director = DirectorUseCase(llm, pb)

        async for _ in director.execute_full(story):
            pass

        expected = 2 + pb.num_beats * 3  # ANALYST + RESOLVER + 3×num_beats (Spec-043)
        assert llm.call_count == expected
