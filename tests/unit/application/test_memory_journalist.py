"""Tests for MemoryJournalist service."""

import pytest

from src.application.services import MemoryJournalist
from src.domain.models import Beat, NarrativeJournal, Story
from src.infrastructure.adapters import MockLLMAdapter


class TestMemoryJournalist:
    """Tests for MemoryJournalist service."""

    @pytest.mark.asyncio
    async def test_update_journal_returns_journal(self):
        """Test that update_journal returns a NarrativeJournal."""
        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="primera_persona",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        beat = Beat(number=1, summary="El protagonista entra", generated_act="Contenido de prueba")

        mock_llm = MockLLMAdapter(
            fixed_response='{"last_events": "Entraron a la casa", "unresolved_mysteries": "", "physical_emotional_state": "Nervioso"}'
        )

        journalist = MemoryJournalist(mock_llm)
        journal = await journalist.update_journal(story, beat)

        assert isinstance(journal, NarrativeJournal)
        assert journal.last_events == "Entraron a la casa"


@pytest.mark.asyncio
async def test_el_journal_llama_al_llm_con_su_rol_y_limites(monkeypatch):
    """Sin `role`, Ollama ignoraba num_ctx/num_predict/stop del rol journal."""
    from unittest.mock import AsyncMock, MagicMock

    from src.config import settings

    monkeypatch.setattr(
        type(settings),
        "role_config",
        lambda _self, _role: {"model": "m", "num_ctx": 4096, "num_predict": 500},
    )
    llm = MagicMock()
    llm.generate = AsyncMock(return_value=MagicMock(text="{}", elapsed_s=0.1))
    story = Story(title="T", protagonista="P", relator="r", sinopsis="S")

    await MemoryJournalist(llm).update_journal(
        story, Beat(number=1, summary="s", generated_act="x")
    )

    kwargs = llm.generate.call_args.kwargs
    assert (kwargs["role"], kwargs["num_ctx"], kwargs["num_predict"]) == ("journal", 4096, 500)
