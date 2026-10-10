"""Spec-650: lo que depende del largo está completo para cada estructura del YAML."""

import typing

import yaml

from src.application.services.authoring import catalog
from src.application.services.beat_spec_repository import BeatSpecRepository
from src.domain.models import StructureId

REPO = BeatSpecRepository()


def test_los_largos_del_dominio_son_los_del_yaml():
    assert set(typing.get_args(StructureId)) == set(REPO.structure_ids)


def test_cada_efecto_tiene_receta_para_cada_largo():
    for sid in REPO.structure_ids:
        for effect in catalog.effects(sid):
            if effect.id != "otro":
                assert effect.planner.strip(), (sid, effect.id)


def test_las_recetas_del_corto_no_nombran_actos_que_no_tiene():
    corto = REPO.estructura("corto")
    for effect in catalog.effects("corto"):
        for n in range(corto.num_actos + 1, 10):
            assert f"acto {n}" not in effect.planner.lower(), (effect.id, n)


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
