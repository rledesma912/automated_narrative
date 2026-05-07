"""Test fixtures."""

from uuid import UUID

from src.domain.models import Beat, NarrativeJournal, Story, StoryStatus


def create_sample_story() -> Story:
    """Create a sample story for testing."""
    return Story(
        id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        title="El Pueblo Olvidado",
        protagonista="Carlos y María",
        relator="primera_persona",
        sinopsis="Dos hermanos regresan al pueblo donde nacieron y descubren secretos oscuros",
        atmosfera="terror_psicologico",
        reglas=["No usar nombres de personajes reales", "Mantener tensión"],
        status=StoryStatus.PENDING,
    )


def create_sample_beat(number: int = 1, summary: str = "Test beat") -> Beat:
    """Create a sample beat for testing."""
    return Beat(
        number=number,
        summary=summary,
        status="pending",
    )


def create_sample_journal() -> NarrativeJournal:
    """Create a sample journal for testing."""
    return NarrativeJournal(
        last_events="Los hermanos llegaron al pueblo",
        unresolved_mysteries="¿Por qué abandonó todo el mundo?",
        physical_emotional_state="Carlos está nervioso, María es escéptica",
    )
