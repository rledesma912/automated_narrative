"""Tests for DirectorUseCase."""

import pytest

from src.application.services import PromptBuilder
from src.application.services.beat_parser import parse_beats
from src.application.use_cases import DirectorUseCase
from src.domain.models import Story, StoryPlan
from src.infrastructure.adapters import MockLLMAdapter


class TestDirectorUseCase:
    """Tests for DirectorUseCase."""

    @pytest.mark.asyncio
    async def test_execute_returns_story_plan(self):
        """Test that execute returns a StoryPlan."""
        story = Story(
            title="Test Story",
            protagonista="Protagonist",
            relator="tercera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        mock_llm = MockLLMAdapter(fixed_response="1. Beat one\n2. Beat two\n3. Beat three")

        prompt_builder = PromptBuilder()
        use_case = DirectorUseCase(mock_llm, prompt_builder)

        result = await use_case.execute(story)

        assert isinstance(result, StoryPlan)
        assert result.title == "Test Story"
        assert result.story_id == story.id

    @pytest.mark.asyncio
    async def test_execute_parses_beats_from_response(self):
        """Test that beats are parsed from LLM response."""
        story = Story(
            title="Test Story",
            protagonista="Protagonist",
            relator="tercera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        mock_llm = MockLLMAdapter(fixed_response="1. Primer beat\n2. Segundo beat\n3. Tercer beat")

        prompt_builder = PromptBuilder()
        use_case = DirectorUseCase(mock_llm, prompt_builder)

        result = await use_case.execute(story)

        assert len(result.beats) == 3
        assert result.beats[0].number == 1
        assert "Primer" in result.beats[0].summary

    @pytest.mark.asyncio
    async def test_execute_returns_default_beats_on_parse_failure(self):
        """Test that default beats are returned when parsing fails."""
        story = Story(
            title="Test Story",
            protagonista="Protagonist",
            relator="tercera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        mock_llm = MockLLMAdapter(fixed_response="")

        prompt_builder = PromptBuilder()
        use_case = DirectorUseCase(mock_llm, prompt_builder)

        result = await use_case.execute(story)

        assert len(result.beats) == 5
        assert result.beats[0].status == "pending"

    @pytest.mark.asyncio
    async def test_generate_6_narrative_beats(self):
        """Test generating 6 narrative beats (Apertura, Incidente, Subida, Crisis, Cumbre, Desenlace)."""
        story = Story(
            title="Test Story",
            protagonista="Protagonist",
            relator="primera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        mock_llm = MockLLMAdapter(
            fixed_response="""1. Apertura: La familia llega a la casa
2. Incidente: El caballo se empaca en la tormenta
3. Subida: Primeras sombras en el bosque
4. Crisis: Apariciones en el camino
5. Cumbre: Todo parece perdido
6. Desenlace: La oración los salva"""
        )

        prompt_builder = PromptBuilder()
        use_case = DirectorUseCase(mock_llm, prompt_builder)

        result = await use_case.execute(story)

        assert len(result.beats) == 6
        assert result.beats[0].summary.startswith("Apertura")
        assert result.beats[1].summary.startswith("Incidente")
        assert result.beats[2].summary.startswith("Subida")
        assert result.beats[3].summary.startswith("Crisis")
        assert result.beats[4].summary.startswith("Cumbre")
        assert result.beats[5].summary.startswith("Desenlace")

    @pytest.mark.asyncio
    async def test_director_uses_injected_normalizer(self):
        """El normalizer inyectado debe ser llamado con el texto raw del LLM."""
        story = Story(
            title="Test",
            protagonista="P",
            relator="tercera",
            escenarios="E",
            sinopsis="S",
            atmosfera="terror",
        )

        class SpyNormalizer:
            def __init__(self):
                self.calls: list[tuple[str, str]] = []

            def normalize(self, text: str, model_name: str = "") -> str:
                self.calls.append((text, model_name))
                return "1. Beat limpio\n2. Otro beat"

        raw = "## Título que debe ser limpiado\n1. Algo sucio\n2. Otro sucio"
        mock_llm = MockLLMAdapter(fixed_response=raw)
        spy = SpyNormalizer()

        use_case = DirectorUseCase(mock_llm, PromptBuilder(), normalizer=spy)
        result = await use_case.execute(story)

        assert len(spy.calls) == 1
        assert spy.calls[0][0] == raw
        assert result.beats[0].summary == "Beat limpio"

    def test_parse_beats_formats_correctly(self):
        """Test _parse_beats parses different formats."""
        story = Story(
            title="Test",
            protagonista="X",
            relator="tercera",
            escenarios="Y",
            sinopsis="Z",
            atmosfera="terror",
        )

        prompt_builder = PromptBuilder()
        use_case = DirectorUseCase(MockLLMAdapter(), prompt_builder)

        beats = parse_beats("1. First beat\n2. Second beat\n3. Third beat", 3, story.id)

        assert len(beats) == 3
        assert beats[0].summary == "First beat"
        assert beats[1].summary == "Second beat"
        assert beats[2].summary == "Third beat"

    def test_parse_beats_formato_N_punto_numero(self):
        """Parser reconoce el formato N.1 que produce mistral/llama."""
        raw = (
            "N.1 La familia llega a la casa.\n"
            "N.2 La fiesta se extiende hasta la noche.\n"
            "N.3 En el monte los sonidos comienzan.\n"
            "N.4 Aparece la figura imposible.\n"
            "N.5 La presión cede y salen al amanecer."
        )
        beats = parse_beats(raw, 5, "story-id")
        assert len(beats) == 5
        assert beats[0].number == 1
        assert "La familia" in beats[0].summary
        assert beats[4].number == 5

    def test_parse_beats_formato_parentesis(self):
        """Parser reconoce el formato 1) Summary."""
        raw = "1) Primer beat\n2) Segundo beat\n3) Tercer beat"
        beats = parse_beats(raw, 3, "story-id")
        assert len(beats) == 3
        assert beats[1].summary == "Segundo beat"

    def test_parse_beats_formato_beat_prefix(self):
        """Parser reconoce el formato Beat 1: Summary."""
        raw = "Beat 1: Exposición inicial\nBeat 2: La transgresión\nBeat 3: El clímax"
        beats = parse_beats(raw, 3, "story-id")
        assert len(beats) == 3
        assert beats[0].summary == "Exposición inicial"

    def test_parse_beats_formato_negrita(self):
        """Parser reconoce el formato **1.** Summary."""
        raw = "**1.** Primera escena\n**2.** Segunda escena"
        beats = parse_beats(raw, 2, "story-id")
        assert len(beats) == 2
        assert beats[0].summary == "Primera escena"

    def test_parse_beats_ignora_duplicados(self):
        """Si el modelo repite el mismo número, solo guarda el primero."""
        raw = "1. Primer beat\n1. Repetición del primero\n2. Segundo beat"
        beats = parse_beats(raw, 2, "story-id")
        assert len(beats) == 2
        assert beats[0].summary == "Primer beat"

    def test_parse_beats_fallback_si_respuesta_ilegible(self):
        """Activa FALLBACK con beats genéricos si ningún patrón matchea."""
        raw = "Lorem ipsum sin números ni formato reconocible"
        beats = parse_beats(raw, 5, "story-id")
        assert len(beats) == 5
        assert all("generado automáticamente" in b.summary for b in beats)

    def test_parse_beats_formato_acto_nombre(self):
        """Parser reconoce el formato 'Acto N (nombre): Summary' que produce mistral."""
        raw = (
            "Acto 1 (exposicion): Una familia llega a casa de María.\n"
            "Acto 2 (accion_ascendente): La fiesta se extiende más de lo previsto.\n"
            "Acto 3 (climax): Entrando en Monte de los Espinillos, el horror se manifiesta.\n"
            "Acto 4 (accion_descendente): En pánico, la familia reza.\n"
            "Acto 5 (desenlace): Llegan al amanecer exhaustos."
        )
        beats = parse_beats(raw, 5, "story-id")
        assert len(beats) == 5
        assert beats[0].number == 1
        assert "Una familia llega" in beats[0].summary
        assert beats[2].number == 3
        assert "horror" in beats[2].summary

    @pytest.mark.asyncio
    async def test_execute_full_yields_beats(self):
        """execute_full() yields one (beat, journal, elapsed) tuple per beat."""
        from unittest.mock import AsyncMock, MagicMock
        from src.domain.models import Beat, NarrativeJournal

        story = Story(
            title="Test",
            protagonista="X",
            relator="tercera_persona",
            escenarios="Y",
            sinopsis="Z",
            atmosfera="terror",
        )

        plan_beats = [
            Beat(number=1, summary="Beat uno", status="pending"),
            Beat(number=2, summary="Beat dos", status="pending"),
        ]
        completed_beat = lambda b: Beat(number=b.number, summary=b.summary, content="Prosa.", status="completed")
        journal = NarrativeJournal(last_events="algo", unresolved_mysteries="", physical_emotional_state="")

        mock_mapper = MagicMock()
        mock_mapper.map = AsyncMock(return_value=plan_beats)

        mock_voz = MagicMock()
        mock_voz.execute = AsyncMock(side_effect=lambda story, beat, **kw: (completed_beat(beat), journal, 1.0))

        director = DirectorUseCase(MockLLMAdapter(), PromptBuilder(), voz=mock_voz)

        # Patch mapper instantiation
        from unittest.mock import patch
        with patch("src.application.use_cases.director_use_case.SynopsisBeatMapper", return_value=mock_mapper):
            results = []
            async for item in director.execute_full(story):
                results.append(item)

        assert len(results) == 2
        assert results[0][0].number == 1
        assert results[0][0].status == "completed"
        assert results[1][0].number == 2

    @pytest.mark.asyncio
    async def test_execute_full_calls_on_plan_ready(self):
        """execute_full() llama on_plan_ready con num_beats y elapsed."""
        from unittest.mock import AsyncMock, MagicMock, patch
        from src.domain.models import Beat, NarrativeJournal

        story = Story(title="T", protagonista="P", relator="r", escenarios="e", sinopsis="s", atmosfera="a")

        plan_beats = [Beat(number=1, summary="b", status="pending")]
        journal = NarrativeJournal()

        mock_mapper = MagicMock()
        mock_mapper.map = AsyncMock(return_value=plan_beats)

        mock_voz = MagicMock()
        mock_voz.execute = AsyncMock(return_value=(
            Beat(number=1, summary="b", content="x", status="completed"), journal, 1.0
        ))

        called_with = []
        def on_plan_ready(n, t):
            called_with.append((n, t))

        director = DirectorUseCase(MockLLMAdapter(), PromptBuilder(), voz=mock_voz)
        with patch("src.application.use_cases.director_use_case.SynopsisBeatMapper", return_value=mock_mapper):
            async for _ in director.execute_full(story, on_plan_ready=on_plan_ready):
                pass

        assert len(called_with) == 1
        assert called_with[0][0] == 1  # num_beats

    @pytest.mark.asyncio
    async def test_execute_narration_yields_completed_beats(self):
        """execute_narration() narra beats pre-existentes y hace yield de cada uno."""
        from unittest.mock import AsyncMock, MagicMock
        from src.domain.models import Beat, NarrativeJournal

        story = Story(title="T", protagonista="P", relator="r", escenarios="e", sinopsis="s", atmosfera="a")
        beats = [Beat(number=i, summary=f"beat {i}", status="pending") for i in range(1, 4)]
        journal = NarrativeJournal()

        mock_voz = MagicMock()
        mock_voz.execute = AsyncMock(side_effect=lambda story, beat, **kw: (
            Beat(number=beat.number, summary=beat.summary, content="narrativa", status="completed"),
            journal, 2.5,
        ))

        director = DirectorUseCase(MockLLMAdapter(), PromptBuilder(), voz=mock_voz)

        results = []
        async for item in director.execute_narration(story, beats):
            results.append(item)

        assert len(results) == 3
        assert all(b.status == "completed" for b, _, _ in results)
        assert mock_voz.execute.call_count == 3
