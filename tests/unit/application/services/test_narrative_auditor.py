"""Tests unitarios para NarrativeAuditor (Spec-170)."""

import pytest

from src.application.services.narrative_auditor import NarrativeAuditor
from src.domain.interfaces import AuditResult


@pytest.fixture
def auditor():
    return NarrativeAuditor()


_GOOD_RESPONSE = """\
## resonance_hamartia
Irene carga con la culpa silenciosa de no haber creído a su madre cuando
le habló de la figura en el monte. Esa grieta ya existía.

## resonance_hybris
La familia ignora la advertencia. Cruzan la tranquera de noche porque
el padre necesita ver el terreno antes del amanecer.

## resonance_anagnorisis
La figura de María inmóvil en el claro, mirando sin parpadear. Los ojos
abiertos pero sin ver.

## resonance_peripeteia
Monte de los Espinillos: espinillos cerrados que cortan la piel de las manos,
barro que succiona los pies, relámpagos mudos.

## resonance_residual
Irene ya no puede cerrar los ojos sin ver el claro iluminado. Duerme con la
luz encendida.
"""

_BOILERPLATE_RESPONSE = """\
## resonance_hamartia
La hamartia es el concepto de la grieta psicológica del protagonista según la
pirámide de Freytag. Se refiere a la vulnerabilidad preexistente.

## resonance_hybris
La hybris es la transgresión. En términos narrativos, este pilar representa
el cruce de la frontera moral.

## resonance_anagnorisis
La anagnórisis es el punto de revelación.

## resonance_peripeteia
La peripeteia es el giro del destino.

## resonance_residual
El daño permanente.
"""

_SYNOPSIS = "La familia llega al campo. Entran al monte de noche. Ven la figura de María inmóvil."


class TestAuditResult:
    def test_returns_audit_result_instance(self, auditor):
        result = auditor.validate(_GOOD_RESPONSE)
        assert isinstance(result, AuditResult)

    def test_good_response_passes(self, auditor):
        result = auditor.validate(_GOOD_RESPONSE, synopsis=_SYNOPSIS)
        assert result.passed is True

    def test_good_response_reason_is_ok(self, auditor):
        result = auditor.validate(_GOOD_RESPONSE, synopsis=_SYNOPSIS)
        assert result.reason == "OK"

    def test_good_response_score_is_positive(self, auditor):
        result = auditor.validate(_GOOD_RESPONSE)
        assert result.score > 0.0

    def test_empty_response_fails(self, auditor):
        result = auditor.validate("")
        assert result.passed is False

    def test_empty_response_score_is_zero(self, auditor):
        result = auditor.validate("")
        assert result.score == 0.0


class TestBoilerplateHeuristic:
    def test_boilerplate_response_fails(self, auditor):
        result = auditor.validate(_BOILERPLATE_RESPONSE)
        assert result.passed is False

    def test_boilerplate_reason_mentions_boilerplate(self, auditor):
        result = auditor.validate(_BOILERPLATE_RESPONSE)
        assert "boilerplate" in result.reason

    def test_phrase_se_refiere_a_triggers(self, auditor):
        result = auditor.validate("## resonance_hamartia\nEsto se refiere a la culpa.")
        assert result.passed is False

    def test_phrase_segun_aristoteles_triggers(self, auditor):
        result = auditor.validate("Según Aristóteles, la hamartia es la falla trágica.")
        assert result.passed is False

    def test_phrase_piramide_freytag_triggers(self, auditor):
        result = auditor.validate("En la pirámide de Freytag este estadio representa el giro.")
        assert result.passed is False

    def test_clean_response_no_boilerplate(self, auditor):
        response = "## resonance_hamartia\nIrene tocó la puerta y sintió el frío en los dedos."
        result = auditor.validate(response)
        assert "boilerplate" not in result.reason


class TestSensorialityHeuristic:
    def test_response_with_sensory_words_passes(self, auditor):
        response = (
            "## resonance_hamartia\nIrene miró el monte y sintió el frío en la piel."
            "\n## resonance_hybris\nCruzaron el barro que succionaba los pies."
        )
        result = auditor.validate(response)
        assert "sensoriality" not in result.reason

    def test_purely_abstract_response_penalizes(self, auditor):
        response = (
            "## resonance_hamartia\nLa vulnerabilidad interna del protagonista.\n"
            "## resonance_hybris\nLa transgresión del límite moral.\n"
            "## resonance_anagnorisis\nEl punto de no retorno emocional.\n"
            "## resonance_peripeteia\nEl entorno adverso.\n"
            "## resonance_residual\nEl cambio permanente de perspectiva.\n"
        )
        result = auditor.validate(response)
        assert "sensoriality" in result.reason


class TestEntropyHeuristic:
    def test_literal_copy_of_synopsis_fails(self, auditor):
        # response is almost identical to synopsis word-for-word
        result = auditor.validate(_SYNOPSIS, synopsis=_SYNOPSIS)
        assert "entropy" in result.reason

    def test_creative_expansion_passes_entropy(self, auditor):
        result = auditor.validate(_GOOD_RESPONSE, synopsis=_SYNOPSIS)
        assert "entropy" not in result.reason

    def test_short_response_skips_entropy_check(self, auditor):
        # menos de 15 palabras → no aplica heurística de entropía
        result = auditor.validate("Irene sintió el frío.", synopsis=_SYNOPSIS)
        assert "entropy" not in result.reason
