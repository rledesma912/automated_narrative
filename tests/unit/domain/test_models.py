"""Tests for domain models."""

from src.domain.models import (
    ActText,
    NarrativeJournal,
    Story,
    StoryStatus,
)


class TestStory:
    """Tests for Story model."""

    def test_create_story(self):
        """Test creating a story."""
        story = Story(
            title="Test Story",
            protagonista="Protagonist",
            relator="tercera_persona",
            sinopsis="Synopsis",
            genero="terror",
        )

        assert story.title == "Test Story"
        assert story.status == StoryStatus.DRAFT
        assert story.id is not None

    def test_story_default_values(self):
        """Test default values."""
        story = Story(
            title="Test",
            protagonista="P",
            relator="R",
            sinopsis="S",
            genero="A",
        )

        assert story.beats == []
        assert story.journal is not None
        assert story.reglas == []


class TestBeat:
    """Tests for Beat model."""

    def test_create_beat(self):
        """Test creating a beat."""
        beat = ActText(number=1, generated_act="Test beat")

        assert beat.number == 1
        assert beat.generated_act == "Test beat"
        assert beat.status == "pending"

    def test_beat_with_content(self):
        """Test beat with content."""
        beat = ActText(
            number=1,
            generated_act="Generated content",
            status="completed",
        )

        assert beat.generated_act == "Generated content"
        assert beat.status == "completed"


class TestNarrativeJournal:
    """Tests for NarrativeJournal model."""

    def test_create_empty_journal(self):
        """Test creating an empty journal."""
        journal = NarrativeJournal()

        assert journal.last_events == ""
        assert journal.physical_emotional_state == ""

    def test_create_journal_with_data(self):
        """Test journal with data."""
        journal = NarrativeJournal(
            last_events="Event occurred",
            emotional_state="Character is scared",
        )

        assert journal.last_events == "Event occurred"

    def test_cuerpo_y_rasgos_cuentan_como_datos(self):
        """Spec-590: una memoria con solo el cuerpo o los rasgos no está vacía."""
        assert NarrativeJournal().is_empty()
        assert not NarrativeJournal(body_state="Un corte en la mano").is_empty()
        assert not NarrativeJournal(narrator_traits=["toma mate"]).is_empty()


class TestMacroBeatBehavior:
    def test_is_narrated_true_cuando_content_y_completed(self):
        beat = ActText(number=1, generated_act="Prosa generada.", status="completed")
        assert beat.is_narrated() is True

    def test_is_narrated_false_sin_content(self):
        beat = ActText(number=1, status="completed")
        assert beat.is_narrated() is False

    def test_is_narrated_false_sin_status_completed(self):
        beat = ActText(number=1, generated_act="Prosa", status="pending")
        assert beat.is_narrated() is False

    def test_is_pending_true_por_defecto(self):
        beat = ActText(number=1, generated_act="T")
        assert beat.is_pending() is True

    def test_is_pending_false_cuando_completed(self):
        beat = ActText(number=1, generated_act="T", status="completed")
        assert beat.is_pending() is False

    def test_has_content_true_con_texto(self):
        beat = ActText(number=1, generated_act="Algo")
        assert beat.has_content() is True

    def test_has_content_false_sin_texto(self):
        beat = ActText(number=1)
        assert beat.has_content() is False

    def test_has_content_independiente_del_status(self):
        beat = ActText(number=1, generated_act="Algo", status="pending")
        assert beat.has_content() is True


class TestStoryBehavior:
    def _story(self, beats=None):
        return Story(
            title="T",
            protagonista="P",
            relator="tercera_persona",
            sinopsis="S",
            genero="a",
            beats=beats or [],
        )

    def test_has_beats_false_sin_beats(self):
        assert self._story().has_beats() is False

    def test_has_beats_true_con_beats(self):
        story = self._story([ActText(number=1, generated_act="T")])
        assert story.has_beats() is True

    def test_beat_count_cero(self):
        assert self._story().beat_count() == 0

    def test_beat_count_correcto(self):
        story = self._story([ActText(number=i, generated_act="T") for i in range(1, 4)])
        assert story.beat_count() == 3

    def test_get_pending_beats_retorna_pendientes(self):
        beats = [
            ActText(number=1, generated_act="X", status="completed"),
            ActText(number=2, generated_act="B"),
            ActText(number=3, generated_act="C"),
        ]
        story = self._story(beats)
        pending = story.get_pending_beats()
        assert len(pending) == 2
        assert all(b.is_pending() for b in pending)

    def test_get_completed_beats_retorna_narrados(self):
        beats = [
            ActText(number=1, generated_act="X", status="completed"),
            ActText(number=2, generated_act="Y", status="completed"),
            ActText(number=3, generated_act="C"),
        ]
        story = self._story(beats)
        completed = story.get_completed_beats()
        assert len(completed) == 2
        assert all(b.is_narrated() for b in completed)

    def test_get_pending_beats_vacio_si_todos_narrados(self):
        beats = [ActText(number=i, generated_act="X", status="completed") for i in range(1, 4)]
        assert self._story(beats).get_pending_beats() == []

    def test_get_completed_beats_vacio_si_ninguno_narrado(self):
        beats = [ActText(number=i, generated_act="A") for i in range(1, 4)]
        assert self._story(beats).get_completed_beats() == []


class TestNarrativeJournalBehavior:
    def test_is_empty_true_cuando_vacio(self):
        assert NarrativeJournal().is_empty() is True

    def test_is_empty_false_con_last_events(self):
        assert NarrativeJournal(last_events="algo").is_empty() is False

    def test_is_empty_false_con_motivos(self):
        assert NarrativeJournal(used_motifs=["el espejo"]).is_empty() is False

    def test_is_empty_false_con_estado(self):
        assert NarrativeJournal(physical_emotional_state="asustado").is_empty() is False

    def test_is_empty_false_con_todo(self):
        j = NarrativeJournal(last_events="E", physical_emotional_state="S")
        assert j.is_empty() is False


class TestStoryAggregate:
    def _story(self, beats=None):
        return Story(
            title="T",
            protagonista="P",
            relator="tercera_persona",
            sinopsis="S",
            genero="a",
            beats=beats or [],
        )

    def test_atmosfera_es_genero_y_subgenero(self):
        story = self._story()
        assert story.atmosfera == "a"
        assert story.model_copy(update={"subgenero": "b"}).atmosfera == "a (b)"

    def test_has_content_false_sin_beats(self):
        assert self._story().has_content is False

    def test_has_content_false_con_beats_sin_prosa(self):
        story = self._story([ActText(number=1)])
        assert story.has_content is False

    def test_has_content_true_con_beat_narrado(self):
        story = self._story([ActText(number=1, generated_act="Prosa")])
        assert story.has_content is True

    def test_get_beat_by_number_existe(self):
        beats = [ActText(number=1, generated_act="A"), ActText(number=3, generated_act="C")]
        story = self._story(beats)
        assert story.get_beat_by_number(3).generated_act == "C"

    def test_get_beat_by_number_no_existe(self):
        story = self._story([ActText(number=1, generated_act="A")])
        assert story.get_beat_by_number(99) is None

    def test_get_beat_by_number_vacio(self):
        assert self._story().get_beat_by_number(1) is None

    def test_get_first_beat_retorna_menor_numero(self):
        beats = [ActText(number=3, generated_act="C"), ActText(number=1, generated_act="A")]
        story = self._story(beats)
        assert story.get_first_beat().number == 1

    def test_get_first_beat_none_sin_beats(self):
        assert self._story().get_first_beat() is None

    def test_get_last_beat_retorna_mayor_numero(self):
        beats = [ActText(number=1, generated_act="A"), ActText(number=5, generated_act="E")]
        story = self._story(beats)
        assert story.get_last_beat().number == 5

    def test_get_last_beat_none_sin_beats(self):
        assert self._story().get_last_beat() is None


# Spec-550 H1: escribir el final es decidirlo.
class TestDirectionFinal:
    def test_con_final_escrito_queda_fijo(self):
        from src.domain.models import Direction

        assert Direction(ending="Le deja flores.").ending_intentional is True
        assert (
            Direction(ending="Le deja flores.", ending_intentional=False).ending_intentional is True
        )

    def test_sin_final_lo_propone_la_ia(self):
        from src.domain.models import Direction

        assert Direction(ending="  ", ending_intentional=True).ending_intentional is False
        assert Direction().ending_intentional is False
