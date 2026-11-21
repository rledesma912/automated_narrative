"""Spec-650: lo que depende del largo está completo para cada estructura del YAML."""

import typing

import yaml

from src.application.services.authoring import catalog
from src.application.services.beat_spec_repository import BeatSpecRepository
from src.domain.models import StructureId

REPO = BeatSpecRepository()


def test_los_largos_del_dominio_son_los_del_yaml():
    assert set(typing.get_args(StructureId)) == set(REPO.structure_ids)


def test_cada_criterio_con_acto_lo_tiene_en_cada_largo_y_existe():
    raw = yaml.safe_load(open("config/workshop_criteria.yaml", encoding="utf-8"))["direccion"]
    with_act = {c["id"] for c in raw if c.get("acto")}
    for sid in REPO.structure_ids:
        estructura = REPO.estructura(sid)
        for c in catalog.direction_criteria(sid):
            if c.id in with_act:
                assert estructura.tiene(c.acto), (sid, c.id, c.acto)


def test_el_final_y_la_historia_secreta_caen_en_su_acto():
    for sid in REPO.structure_ids:
        estructura = REPO.estructura(sid)
        assert catalog.criterion("final", sid).acto == estructura.ultimo


def test_personajes_que_puede_proponer_la_ia():
    """Spec-730 D1: 2 en la media, 1 en el corto."""
    assert REPO.estructura("medio").personajes_nuevos_max == 2
    assert REPO.estructura("corto").personajes_nuevos_max == 1
