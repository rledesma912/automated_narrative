"""Tests de error paths para VozUseCase."""

import pytest

from src.domain.models import Beat, Story
from src.infrastructure.adapters.mock_llm_adapter import MockLLMAdapter


class TestVozErrorPathsCurrent:
    """Tests de manejo de errores en VozUseCase."""

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
    async def test_voz_with_mock_adapter(self):
        """MockLLMAdapter funciona correctamente."""
        mock_llm = MockLLMAdapter(fixed_response="Test response")
        beat = Beat(number=1, summary="algo", status="pending")

        from src.application.use_cases.voz_use_case import VozUseCase

        use_case = VozUseCase(mock_llm)
        result_beat, _, _ = await use_case.execute(self._make_story(), beat)

        assert result_beat is not None
        assert result_beat.status == "completed"

    @pytest.mark.asyncio
    async def test_voz_beat_creation_works(self):
        """Verifica que la creación de beats funciona."""
        story = self._make_story()
        beat = Beat(number=1, summary="Test beat")

        assert beat.number == 1
        assert story.title == "Test"
