"""Integration tests for core flow: Parser → Director → Voz."""

import pytest

from src.application.services import PromptBuilder
from src.application.use_cases import DirectorUseCase, VozUseCase
from src.domain.models import Beat, Story
from src.infrastructure.adapters import MockLLMAdapter
from src.infrastructure.parsers import MarkdownStoryParser


class TestCoreFlowWithMocks:
    """Test the complete flow with mocks."""

    @pytest.mark.asyncio
    async def test_parser_to_director_flow(self):
        """Test: Parser extracts data → Director generates beats."""
        parser = MarkdownStoryParser(input_dir=None)

        content = """# Test Story

**Protagonistas**: Juan, Maria
**relator**: Pedro
**Escenarios**: Casa abandonada
**Sinopsis**: Historia de terror

---

## Las reglas de la historia
- No hay reglas
"""

        story_data = parser._extract_data(content, "test_story")

        cleaned_protagonista = parser._clean_markdown(story_data.protagonista)
        cleaned_escenarios = parser._clean_markdown(story_data.escenarios)

        assert "Juan" in cleaned_protagonista
        assert "Maria" in cleaned_protagonista
        assert "casa" in cleaned_escenarios.lower()

        story = Story(
            title=story_data.title,
            protagonista=cleaned_protagonista,
            relator=story_data.relator,
            escenarios=cleaned_escenarios,
            sinopsis=story_data.sinopsis,
            atmosfera="terror",
        )

        mock_llm = MockLLMAdapter(
            fixed_response="""1. Apertura: La familia llega
2. Incidente: Algo sucede
3. Subida: La tensión crece
4. Crisis: El horror se manifiesta
5. Cumbre: Todo parece perdido
6. Desenlace: La resolución"""
        )

        prompt_builder = PromptBuilder()
        director = DirectorUseCase(mock_llm, prompt_builder)

        plan = await director.execute(story, num_beats=6)

        assert len(plan.beats) == 6
        assert plan.beats[0].summary.startswith("Apertura")
        assert plan.beats[5].summary.startswith("Desenlace")

    @pytest.mark.asyncio
    async def test_director_to_voz_flow(self):
        """Test: Director generates beats → Voz narrates each beat."""
        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="primera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        mock_llm = MockLLMAdapter(fixed_response="1. Beat uno\n2. Beat dos\n3. Beat tres")
        prompt_builder = PromptBuilder()

        director = DirectorUseCase(mock_llm, prompt_builder)
        plan = await director.execute(story, num_beats=3)

        assert len(plan.beats) == 3

        mock_llm_voice = MockLLMAdapter(fixed_response="Contenido narrado")
        voz = VozUseCase(mock_llm_voice)

        completed_beats = []
        for beat in plan.beats:
            narrated_beat, journal = await voz.execute(story, beat)
            completed_beats.append(narrated_beat)

        assert len(completed_beats) == 3
        assert all(b.status == "completed" for b in completed_beats)
        assert all(b.content == "Contenido narrado" for b in completed_beats)

    @pytest.mark.asyncio
    async def test_full_flow_end_to_end(self):
        """Test: Complete flow from input file content to narrated beats."""
        parser = MarkdownStoryParser(input_dir=None)

        content = """# El Monte

**Protagonistas**: Ricardo padre, Irene madre
**relator**: Irene
**Escenarios**: Monte prohibido
**Sinopsis**: Familia en peligro

---

## Las reglas de la historia
- Ricardo es escéptico
"""

        story_data = parser._extract_data(content, "el_monte")

        story = Story(
            title=story_data.title,
            protagonista=story_data.protagonista,
            relator=story_data.relator,
            escenarios=story_data.escenarios,
            sinopsis=story_data.sinopsis,
            atmosfera="terror psicológico",
        )

        mock_director = MockLLMAdapter(
            fixed_response="""1. Apertura: La familia-sale
2. Incidente: Tormenta
3. Subida: Sombras
4. Crisis: Apariciones
5. Cumbre: Oración
6. Desenlace: Salida"""
        )

        mock_voz = MockLLMAdapter(fixed_response="Prosa narrada")

        prompt_builder = PromptBuilder()
        director = DirectorUseCase(mock_director, prompt_builder)

        plan = await director.execute(story, num_beats=6)

        assert len(plan.beats) == 6

        voz = VozUseCase(mock_voz)
        completed = []

        for beat in plan.beats:
            narrated, _ = await voz.execute(story, beat)
            completed.append(narrated)

        assert len(completed) == 6
        assert all(b.status == "completed" for b in completed)
        assert all(b.content == "Prosa narrada" for b in completed)

    @pytest.mark.asyncio
    async def test_6_narrative_beats_generation(self):
        """Test: Generate exactly 6 narrative beats matching story structure."""
        story = Story(
            title="Test",
            protagonista="Familia",
            relator="primera_persona",
            escenarios="Casa de campo",
            sinopsis="Historia de terror",
            atmosfera="terror",
        )

        mock_llm = MockLLMAdapter(
            fixed_response="""1. Apertura: La familia llega a la casa
2. Incidente: El caballo se empaca
3. Subida: Primeras sombras aparecen
4. Crisis: Las apariciones se manifiestan
5. Cumbre: Todo parece perdido
6. Desenlace: La oración los salva"""
        )

        prompt_builder = PromptBuilder()
        director = DirectorUseCase(mock_llm, prompt_builder)

        plan = await director.execute(story, num_beats=6)

        beats = plan.beats

        assert len(beats) == 6
        assert beats[0].summary.startswith("Apertura")
        assert beats[1].summary.startswith("Incidente")
        assert beats[2].summary.startswith("Subida")
        assert beats[3].summary.startswith("Crisis")
        assert beats[4].summary.startswith("Cumbre")
        assert beats[5].summary.startswith("Desenlace")

        for beat in beats:
            assert beat.status == "pending"
            assert beat.content == ""
