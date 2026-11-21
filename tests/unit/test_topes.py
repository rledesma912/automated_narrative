"""Spec-760: los topes del asistente viven en un solo lugar y alcanzan a lo que se pide."""

from src.application.services.authoring import catalog
from src.application.services.beat_spec_repository import BeatSpecRepository
from src.domain.models import Entity
from src.presentation.schemas.authoring import ActForm, DirectionForm, ThreatForm
from src.presentation.validation import miles

TOPES = catalog.topes()


def _max(model, field: str) -> int:
    meta = model.model_fields[field].metadata
    return next(m.max_length for m in meta if hasattr(m, "max_length"))


def test_los_hechos_de_un_acto_alcanzan_a_lo_que_pide_cada_estructura():
    repo = BeatSpecRepository()
    pedidos = [
        a.get("hechos_max", 0) for sid in repo.structure_ids for a in repo.estructura(sid).actos
    ]
    assert TOPES["events"] > max(pedidos)


def test_el_schema_usa_los_topes_de_config():
    assert _max(DirectionForm, "premise") == TOPES["premise"] == 20000
    assert _max(DirectionForm, "title") == TOPES["title"]
    assert _max(ActForm, "events") == TOPES["events"]
    assert _max(ActForm, "goal") == TOPES["goal"]


def test_la_amenaza_tiene_los_mismos_topes_que_la_entidad():
    """La amenaza del formulario es la entidad principal del dominio (Spec-450)."""
    for campo, de_entidad in [
        ("name", "name"),
        ("description", "description"),
        ("manifestations", "manifestations"),
        ("limits", "limits"),
    ]:
        assert _max(ThreatForm, campo) == _max(Entity, de_entidad) == TOPES[f"threat_{campo}"]


def test_miles():
    assert (miles(800), miles(21300), miles(1000000)) == ("800", "21.300", "1.000.000")
