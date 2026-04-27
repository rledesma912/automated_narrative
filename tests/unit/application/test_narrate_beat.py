"""Tests for VozUseCase."""

import pytest

from src.application.services.narrator_retry_generator import NarratorRetryGenerator
from src.application.use_cases import VozUseCase
from src.domain.interfaces import LLMResponse
from src.domain.models import Beat, MacroBeat, NarrativeJournal, Story
from src.infrastructure.adapters import MockLLMAdapter


class TestVozUseCase:
    """Tests for VozUseCase."""

    @pytest.mark.asyncio
    async def test_execute_returns_beat_and_journal(self):
        """Test that execute returns tuple of Beat and NarrativeJournal."""
        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="primera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        beat = Beat(number=1, summary="El protagonista entra", status="pending")

        mock_llm = MockLLMAdapter(fixed_response="Contenido generado")

        use_case = VozUseCase(mock_llm)

        result_beat, result_journal, llm_elapsed = await use_case.execute(story, beat)

        assert isinstance(result_beat, Beat)
        assert result_beat.content == "Contenido generado"
        assert result_beat.status == "completed"
        assert isinstance(result_journal, NarrativeJournal)
        assert isinstance(llm_elapsed, float)

    @pytest.mark.asyncio
    async def test_execute_updates_beat_content(self):
        """Test that beat content is updated after execution."""
        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="primera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        beat = Beat(number=1, summary="El protagonista entra", status="pending")

        mock_llm = MockLLMAdapter(fixed_response="El jeep se detuvo en la entrada...")
        use_case = VozUseCase(mock_llm)

        result_beat, _, _ = await use_case.execute(story, beat)

        assert result_beat.content == "El jeep se detuvo en la entrada..."
        assert result_beat.status == "completed"

    @pytest.mark.asyncio
    async def test_execute_with_previous_beats(self):
        """Test execution with previous beats for context."""
        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="primera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        previous_beats = [
            Beat(number=1, summary="Beat 1", content="Contenido 1", status="completed"),
            Beat(number=2, summary="Beat 2", content="Contenido 2", status="completed"),
        ]

        beat = Beat(number=3, summary="Beat 3", status="pending")

        mock_llm = MockLLMAdapter(fixed_response="Contenido nuevo")
        use_case = VozUseCase(mock_llm)

        result_beat, _, _ = await use_case.execute(story, beat, previous_beats=previous_beats)

        assert mock_llm.call_count >= 1

    @pytest.mark.asyncio
    async def test_execute_injects_journal_context(self):
        """Test that journal context is injected into prompt."""
        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="primera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        beat = Beat(number=1, summary="Beat 1", status="pending")

        journal = NarrativeJournal(
            last_events="El protagonista entró a la casa",
            unresolved_mysteries="¿Por qué está abandonada?",
            physical_emotional_state="Nervioso",
        )

        mock_llm = MockLLMAdapter(fixed_response="Contenido")
        use_case = VozUseCase(mock_llm)

        result_beat, result_journal, _ = await use_case.execute(story, beat, journal=journal)

        assert isinstance(result_journal, NarrativeJournal)

    @pytest.mark.asyncio
    async def test_voz_uses_injected_normalizer(self):
        """El normalizer inyectado limpia el texto raw antes de asignarlo al beat."""
        story = Story(
            title="Test",
            protagonista="P",
            relator="primera_persona",
            escenarios="L",
            sinopsis="S",
            atmosfera="terror",
        )

        class SpyNormalizer:
            def __init__(self):
                self.calls: list[tuple[str, str]] = []

            def normalize(self, text: str, model_name: str = "") -> str:
                self.calls.append((text, model_name))
                return "CONTENIDO LIMPIO"

        raw = "## Encabezado feo\n\nTexto original."
        mock_llm = MockLLMAdapter(fixed_response=raw)
        spy = SpyNormalizer()

        beat = Beat(number=1, summary="algo", status="pending")
        use_case = VozUseCase(mock_llm, normalizer=spy)

        result_beat, _, _ = await use_case.execute(story, beat)

        assert spy.calls, "Normalizer no fue invocado"
        assert spy.calls[0][0] == raw
        assert result_beat.content == "CONTENIDO LIMPIO"

    @pytest.mark.asyncio
    async def test_narrate_all_6_beats_sequentially(self):
        """Test narrating all 6 beats in sequence maintains context."""
        story = Story(
            title="Test",
            protagonista="Familia",
            relator="primera_persona",
            escenarios="Casa de campo",
            sinopsis="Historia de terror",
            atmosfera="terror psicológico",
        )

        beats = [Beat(number=i, summary=f"Beat {i}", status="pending") for i in range(1, 7)]

        completed = []
        journal = None

        mock_llm = MockLLMAdapter(fixed_response="Contenido narrado")
        use_case = VozUseCase(mock_llm)

        for beat in beats:
            result_beat, result_journal, _ = await use_case.execute(
                story, beat, previous_beats=completed, journal=journal
            )
            completed.append(result_beat)
            journal = result_journal

        assert len(completed) == 6
        assert all(b.status == "completed" for b in completed)
        assert all(b.content == "Contenido narrado" for b in completed)


class TestVozErrorPaths:
    """Error path tests para VozUseCase."""

    def _make_story(self) -> Story:
        return Story(
            title="Test",
            protagonista="P",
            relator="primera_persona",
            escenarios="L",
            sinopsis="S",
            atmosfera="terror",
        )

    @pytest.mark.asyncio
    async def test_voz_empty_response(self):
        """LLM retorna texto vacío — beat se marca completed con content vacío."""
        mock_llm = MockLLMAdapter(fixed_response="")
        beat = Beat(number=1, summary="algo", status="pending")

        use_case = VozUseCase(mock_llm)
        result_beat, _, _ = await use_case.execute(self._make_story(), beat)

        assert result_beat.status == "completed"
        assert result_beat.content == ""

    @pytest.mark.asyncio
    async def test_voz_refusal_triggers_retry(self):
        """Modelo hace refusal en primer intento — NarratorRetryGenerator reintenta."""
        responses = ["Lo siento, no puedo escribir eso.", "El viejo molino crujía."]
        call_count = 0

        class SequentialMock:
            async def generate(self, prompt, **kwargs):
                nonlocal call_count
                text = responses[min(call_count, len(responses) - 1)]
                call_count += 1
                return LLMResponse(text=text, context=None)

            async def close(self):
                pass

        beat = Beat(number=1, summary="algo", status="pending")
        use_case = VozUseCase(SequentialMock())
        result_beat, _, _ = await use_case.execute(self._make_story(), beat)

        assert call_count >= 2, "Debe haber reintentado al detectar refusal"
        assert "molino" in result_beat.content

    @pytest.mark.asyncio
    async def test_voz_malformed_response_is_normalized(self):
        """Respuesta con caracteres de encabezado markdown — normalizer los limpia."""
        raw = "## Título indeseado\n\nTexto del relato."
        mock_llm = MockLLMAdapter(fixed_response=raw)
        beat = Beat(number=1, summary="algo", status="pending")

        class StripHeadingsNormalizer:
            def normalize(self, text: str, model_name: str = "") -> str:
                import re
                return re.sub(r"^##.*\n\n", "", text)

        use_case = VozUseCase(mock_llm, normalizer=StripHeadingsNormalizer())
        result_beat, _, _ = await use_case.execute(self._make_story(), beat)

        assert not result_beat.content.startswith("##")
        assert "Texto del relato." in result_beat.content

    @pytest.mark.asyncio
    async def test_voz_narrate_empty_response(self):
        """narrate() con respuesta vacía — macro_beat.content queda vacío, status completed."""
        mock_llm = MockLLMAdapter(fixed_response="")
        macro_beat = MacroBeat(
            number=1,
            summary="algo",
            status="pending",
            narrative_context="Contexto de prueba",
        )
        use_case = VozUseCase(mock_llm)
        result, _ = await use_case.narrate(macro_beat, self._make_story())

        assert result.status == "completed"
        assert result.content == ""
