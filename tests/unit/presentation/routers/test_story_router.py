"""Tests de `_request_to_dto`: contrato del wizard web → StoryCreateDTO.

El wizard envía `storyteller_config` (no `narrator_config`) y no manda
`genero`/`subgenero`/`tono` explícitos: vienen dentro de `atmosphere`.
"""

from src.application.services.narrator_config_sanitizer import (
    extract_actos,
    extract_atmosphere,
)
from src.presentation.routers.story_router import _request_to_dto
from src.presentation.schemas.request import StoryCreateRequest


def _wizard_payload(**overrides) -> dict:
    """Payload con la forma exacta de `mapWizardToCore()` del frontend."""
    payload = {
        "title": "La pena del colectivo",
        "protagonista": "Irene: narradora [audaz]",
        "relator": "Primera persona en pasado. Narrador: Irene.",
        "escenarios": "Casa: vieja y húmeda",
        "sinopsis": "acto 1\n\nacto 2",
        "atmosfera": "folk_horror (rural) - creciente",
        "reglas": ["No mirar el espejo"],
        "actos": {"act_1": {"type": "exposicion", "text": "acto 1"}},
        "storyteller_config": {
            "storyteller_id": "P1",
            "voice_style": "intimista",
            "atmosphere": {"genre": "folk_horror", "subgenre": "rural", "tone": "creciente"},
            "scenarios": [
                {"id": "S1", "order": 1, "name": "Casa", "description": "vieja y húmeda"}
            ],
            "rules": [{"id": "R1", "text": "No mirar el espejo", "type": "paranormal"}],
            "actos": {
                "act_1": {"type": "exposicion", "text": "acto 1"},
                "act_2": {"type": "accion_ascendente", "text": "acto 2"},
            },
            "perception": {"reliability": "subjetiva"},
        },
        "personajes_full": [
            {"id": "P1", "name": "Irene", "role": "narradora", "traits": ["audaz"]}
        ],
    }
    payload.update(overrides)
    return payload


def test_storyteller_config_se_acepta_como_narrator_config():
    dto = _request_to_dto(StoryCreateRequest(**_wizard_payload()))

    assert dto.narrator_config == {
        "storyteller_id": "P1",
        "voice_style": "intimista",
        "perception": {"reliability": "subjetiva"},
    }


def test_genero_subgenero_tono_se_derivan_de_atmosphere():
    dto = _request_to_dto(StoryCreateRequest(**_wizard_payload()))

    assert (dto.genero, dto.subgenero, dto.tono) == ("folk_horror", "rural", "creciente")


def test_genero_explicito_tiene_prioridad_sobre_atmosphere():
    dto = _request_to_dto(StoryCreateRequest(**_wizard_payload(genero="suspenso", tono="ambiguo")))

    assert (dto.genero, dto.subgenero, dto.tono) == ("suspenso", "rural", "ambiguo")


def test_escenarios_con_descripcion_y_reglas_tipadas():
    dto = _request_to_dto(StoryCreateRequest(**_wizard_payload()))

    assert dto.escenarios_full == [{"name": "Casa", "description": "vieja y húmeda"}]
    assert dto.typed_rules == [{"id": "R1", "content": "No mirar el espejo", "type": "paranormal"}]


def test_actos_se_extraen_de_storyteller_config():
    dto = _request_to_dto(StoryCreateRequest(**_wizard_payload()))

    assert len(dto.actos) == 5
    assert dto.actos[0] == {"number": 1, "type": "exposicion", "synopsis": "acto 1"}
    assert dto.actos[1]["synopsis"] == "acto 2"
    assert dto.actos[4] == {"number": 5, "type": "", "synopsis": ""}


def test_sin_config_no_inventa_datos():
    payload = _wizard_payload()
    del payload["storyteller_config"]
    dto = _request_to_dto(StoryCreateRequest(**payload))

    assert dto.narrator_config is None
    assert (dto.genero, dto.subgenero, dto.tono) == ("", "", "")
    assert dto.actos == []


def test_narrator_config_por_su_nombre_sigue_funcionando():
    payload = _wizard_payload()
    payload["narrator_config"] = payload.pop("storyteller_config")
    dto = _request_to_dto(StoryCreateRequest(**payload))

    assert dto.genero == "folk_horror"
    assert dto.narrator_config["storyteller_id"] == "P1"


def test_extract_atmosphere_y_actos_con_config_vacio():
    assert extract_atmosphere(None) == ("", "", "")
    assert extract_atmosphere({"atmosphere": None}) == ("", "", "")
    assert [a["synopsis"] for a in extract_actos({})] == ["", "", "", "", ""]
