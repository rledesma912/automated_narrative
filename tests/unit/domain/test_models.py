"""Tests for domain models."""

from src.domain.models import Beat, MacroBeat, NarrativeJournal, Story, StoryStatus


class TestStory:
    """Tests for Story model."""

    def test_create_story(self):
        """Test creating a story."""
        story = Story(
            title="Test Story",
            protagonista="Protagonist",
            relator="tercera_persona",
            escenarios="Location",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        assert story.title == "Test Story"
        assert story.status == StoryStatus.PENDING
        assert story.id is not None

    def test_story_default_values(self):
        """Test default values."""
        story = Story(
            title="Test",
            protagonista="P",
            relator="R",
            escenarios="E",
            sinopsis="S",
            atmosfera="A",
        )

        assert story.beats == []
        assert story.journal is not None
        assert story.reglas == []


class TestBeat:
    """Tests for Beat model."""

    def test_create_beat(self):
        """Test creating a beat."""
        beat = Beat(number=1, summary="Test beat")

        assert beat.number == 1
        assert beat.summary == "Test beat"
        assert beat.status == "pending"
        assert beat.content == ""

    def test_beat_with_content(self):
        """Test beat with content."""
        beat = Beat(
            number=1,
            summary="Test summary",
            content="Generated content",
            status="completed",
        )

        assert beat.content == "Generated content"
        assert beat.status == "completed"


class TestNarrativeJournal:
    """Tests for NarrativeJournal model."""

    def test_create_empty_journal(self):
        """Test creating an empty journal."""
        journal = NarrativeJournal()

        assert journal.last_events == ""
        assert journal.unresolved_mysteries == ""
        assert journal.physical_emotional_state == ""

    def test_create_journal_with_data(self):
        """Test journal with data."""
        journal = NarrativeJournal(
            last_events="Event occurred",
            unresolved_mysteries="Mystery question",
            emotional_state="Character is scared",
        )

        assert journal.last_events == "Event occurred"
