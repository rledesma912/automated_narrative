"""Tests for domain models."""


from src.domain.models import Beat, MacroBeat, NarrativeJournal, Story, StoryMetadata, StoryStatus


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


class TestMacroBeatBehavior:

    def test_is_narrated_true_cuando_content_y_completed(self):
        beat = MacroBeat(number=1, summary="T", content="Prosa generada.", status="completed")
        assert beat.is_narrated() is True

    def test_is_narrated_false_sin_content(self):
        beat = MacroBeat(number=1, summary="T", status="completed")
        assert beat.is_narrated() is False

    def test_is_narrated_false_sin_status_completed(self):
        beat = MacroBeat(number=1, summary="T", content="Prosa", status="pending")
        assert beat.is_narrated() is False

    def test_is_pending_true_por_defecto(self):
        beat = MacroBeat(number=1, summary="T")
        assert beat.is_pending() is True

    def test_is_pending_false_cuando_completed(self):
        beat = MacroBeat(number=1, summary="T", status="completed")
        assert beat.is_pending() is False

    def test_has_content_true_con_texto(self):
        beat = MacroBeat(number=1, summary="T", content="Algo")
        assert beat.has_content() is True

    def test_has_content_false_sin_texto(self):
        beat = MacroBeat(number=1, summary="T")
        assert beat.has_content() is False

    def test_has_content_independiente_del_status(self):
        beat = MacroBeat(number=1, summary="T", content="Algo", status="pending")
        assert beat.has_content() is True


class TestStoryBehavior:

    def _story(self, beats=None):
        return Story(
            title="T", protagonista="P", relator="tercera_persona",
            sinopsis="S", atmosfera="a", beats=beats or [],
        )

    def test_has_beats_false_sin_beats(self):
        assert self._story().has_beats() is False

    def test_has_beats_true_con_beats(self):
        story = self._story([MacroBeat(number=1, summary="T")])
        assert story.has_beats() is True

    def test_beat_count_cero(self):
        assert self._story().beat_count() == 0

    def test_beat_count_correcto(self):
        story = self._story([MacroBeat(number=i, summary="T") for i in range(1, 4)])
        assert story.beat_count() == 3

    def test_get_pending_beats_retorna_pendientes(self):
        beats = [
            MacroBeat(number=1, summary="A", content="X", status="completed"),
            MacroBeat(number=2, summary="B"),
            MacroBeat(number=3, summary="C"),
        ]
        story = self._story(beats)
        pending = story.get_pending_beats()
        assert len(pending) == 2
        assert all(b.is_pending() for b in pending)

    def test_get_completed_beats_retorna_narrados(self):
        beats = [
            MacroBeat(number=1, summary="A", content="X", status="completed"),
            MacroBeat(number=2, summary="B", content="Y", status="completed"),
            MacroBeat(number=3, summary="C"),
        ]
        story = self._story(beats)
        completed = story.get_completed_beats()
        assert len(completed) == 2
        assert all(b.is_narrated() for b in completed)

    def test_get_pending_beats_vacio_si_todos_narrados(self):
        beats = [MacroBeat(number=i, summary="A", content="X", status="completed") for i in range(1, 4)]
        assert self._story(beats).get_pending_beats() == []

    def test_get_completed_beats_vacio_si_ninguno_narrado(self):
        beats = [MacroBeat(number=i, summary="A") for i in range(1, 4)]
        assert self._story(beats).get_completed_beats() == []


class TestNarrativeJournalBehavior:

    def test_is_empty_true_cuando_vacio(self):
        assert NarrativeJournal().is_empty() is True

    def test_is_empty_false_con_last_events(self):
        assert NarrativeJournal(last_events="algo").is_empty() is False

    def test_is_empty_false_con_unresolved(self):
        assert NarrativeJournal(unresolved_mysteries="?").is_empty() is False

    def test_is_empty_false_con_estado(self):
        assert NarrativeJournal(physical_emotional_state="asustado").is_empty() is False

    def test_is_empty_false_con_todo(self):
        j = NarrativeJournal(last_events="E", unresolved_mysteries="?", physical_emotional_state="S")
        assert j.is_empty() is False


class TestStoryMetadata:

    def _story(self, **kwargs):
        defaults = dict(
            title="T", protagonista="Irene", relator="tercera_persona",
            sinopsis="Una historia de terror.", atmosfera="oscura",
            reglas=["Regla A"], storyteller_config={"voz": "primera"},
        )
        defaults.update(kwargs)
        return Story(**defaults)

    def test_from_story_copia_protagonista(self):
        m = StoryMetadata.from_story(self._story())
        assert m.protagonista == "Irene"

    def test_from_story_copia_relator(self):
        m = StoryMetadata.from_story(self._story())
        assert m.relator == "tercera_persona"

    def test_from_story_copia_sinopsis(self):
        m = StoryMetadata.from_story(self._story())
        assert m.sinopsis == "Una historia de terror."

    def test_from_story_copia_atmosfera(self):
        m = StoryMetadata.from_story(self._story())
        assert m.atmosfera == "oscura"

    def test_from_story_copia_reglas(self):
        m = StoryMetadata.from_story(self._story())
        assert m.reglas == ["Regla A"]

    def test_from_story_copia_storyteller_config(self):
        m = StoryMetadata.from_story(self._story())
        assert m.storyteller_config == {"voz": "primera"}

    def test_has_rules_true_con_reglas(self):
        m = StoryMetadata(protagonista="P", relator="r", sinopsis="s",
                          atmosfera="a", reglas=["x"])
        assert m.has_rules() is True

    def test_has_rules_true_con_storyteller_config(self):
        m = StoryMetadata(protagonista="P", relator="r", sinopsis="s",
                          atmosfera="a", storyteller_config={"k": "v"})
        assert m.has_rules() is True

    def test_has_rules_false_sin_nada(self):
        m = StoryMetadata(protagonista="P", relator="r", sinopsis="s", atmosfera="a")
        assert m.has_rules() is False


class TestStoryAggregate:

    def _story(self, beats=None):
        return Story(
            title="T", protagonista="P", relator="tercera_persona",
            sinopsis="S", atmosfera="a", beats=beats or [],
        )

    def test_metadata_property_retorna_story_metadata(self):
        from src.domain.models import StoryMetadata
        story = self._story()
        assert isinstance(story.metadata, StoryMetadata)

    def test_metadata_refleja_campos_actuales(self):
        story = self._story()
        assert story.metadata.protagonista == story.protagonista

    def test_has_content_false_sin_beats(self):
        assert self._story().has_content is False

    def test_has_content_false_con_beats_sin_prosa(self):
        story = self._story([MacroBeat(number=1, summary="T")])
        assert story.has_content is False

    def test_has_content_true_con_beat_narrado(self):
        story = self._story([MacroBeat(number=1, summary="T", content="Prosa")])
        assert story.has_content is True

    def test_get_beat_by_number_existe(self):
        beats = [MacroBeat(number=1, summary="A"), MacroBeat(number=3, summary="C")]
        story = self._story(beats)
        assert story.get_beat_by_number(3).summary == "C"

    def test_get_beat_by_number_no_existe(self):
        story = self._story([MacroBeat(number=1, summary="A")])
        assert story.get_beat_by_number(99) is None

    def test_get_beat_by_number_vacio(self):
        assert self._story().get_beat_by_number(1) is None

    def test_get_first_beat_retorna_menor_numero(self):
        beats = [MacroBeat(number=3, summary="C"), MacroBeat(number=1, summary="A")]
        story = self._story(beats)
        assert story.get_first_beat().number == 1

    def test_get_first_beat_none_sin_beats(self):
        assert self._story().get_first_beat() is None

    def test_get_last_beat_retorna_mayor_numero(self):
        beats = [MacroBeat(number=1, summary="A"), MacroBeat(number=5, summary="E")]
        story = self._story(beats)
        assert story.get_last_beat().number == 5

    def test_get_last_beat_none_sin_beats(self):
        assert self._story().get_last_beat() is None
