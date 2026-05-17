"""Tests for DirectorUseCase y el parser de beats compartido."""

import pytest

from src.application.services import PromptBuilder
from src.application.services.beat_parser import parse_beats
from src.application.use_cases import DirectorUseCase
from src.domain.models import Story
from src.infrastructure.adapters import MockLLMAdapter


class TestBeatParser:
    """Tests del parser de beats compartido (parse_beats)."""

    def test_parse_beats_formats_correctly(self):
        """parse_beats parsea el formato '1. Summary'."""
        story = Story(
            title="Test",
            protagonista="X",
            relator="tercera",
            sinopsis="Z",
            atmosfera="terror",
        )
        beats = parse_beats("1. First beat\n2. Second beat\n3. Third beat", 3, story.id)

        assert len(beats) == 3
        assert beats[0].summary == "First beat"
        assert beats[1].summary == "Second beat"
        assert beats[2].summary == "Third beat"

    def test_parse_beats_formato_n_punto_numero(self):
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


class TestDirectorExecuteNarration:
    """Tests de DirectorUseCase.execute_narration()."""

    @pytest.mark.asyncio
    async def test_execute_narration_yields_completed_beats(self):
        """execute_narration() narra beats pre-existentes y hace yield de cada uno."""
        from unittest.mock import AsyncMock, MagicMock

        from src.domain.models import Beat, NarrativeJournal

        story = Story(
            title="T",
            protagonista="P",
            relator="r",
            sinopsis="s",
            atmosfera="a",
        )
        beats = [Beat(number=i, summary=f"beat {i}", status="pending") for i in range(1, 4)]
        journal = NarrativeJournal()

        mock_voz = MagicMock()
        mock_voz.execute = AsyncMock(
            side_effect=lambda story, beat, **kw: (  # noqa: ARG005
                Beat(
                    number=beat.number,
                    summary=beat.summary,
                    generated_act="narrativa",
                    status="completed",
                ),
                journal,
                2.5,
            )
        )

        director = DirectorUseCase(MockLLMAdapter(), PromptBuilder(), voz=mock_voz)

        results = []
        async for item in director.execute_narration(story, beats):
            results.append(item)

        assert len(results) == 3
        assert all(b.status == "completed" for b, _, _ in results)
        assert mock_voz.execute.call_count == 3
