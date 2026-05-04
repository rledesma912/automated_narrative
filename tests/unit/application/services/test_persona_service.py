"""Tests para PersonaService — Spec 063 Slice C."""

import pytest

from src.application.services.persona_service import PersonaService


@pytest.fixture
def svc() -> PersonaService:
    return PersonaService()


class TestPersonaService:
    def test_tercera_persona(self, svc):
        assert svc.resolve("tercera_persona") == "tercera persona"

    def test_tercera_alias(self, svc):
        assert svc.resolve("tercera") == "tercera persona"

    def test_segunda_persona(self, svc):
        assert svc.resolve("segunda_persona") == "segunda persona"

    def test_segunda_alias(self, svc):
        assert svc.resolve("segunda") == "segunda persona"

    def test_primera_persona(self, svc):
        assert svc.resolve("primera_persona") == "primera persona"

    def test_primera_alias(self, svc):
        assert svc.resolve("primera") == "primera persona"

    def test_nombre_irene(self, svc):
        # Sin detección de género: devuelve el nombre tal cual
        assert svc.resolve("irene") == "primera persona (irene narra)"

    def test_nombre_irene_case_insensitive(self, svc):
        assert svc.resolve("Irene") == "primera persona (Irene narra)"

    def test_nombre_laura(self, svc):
        assert svc.resolve("laura") == "primera persona (laura narra)"

    def test_nombre_ricardo(self, svc):
        assert svc.resolve("ricardo") == "primera persona (ricardo narra)"

    def test_nombre_juan(self, svc):
        assert svc.resolve("juan") == "primera persona (juan narra)"

    def test_nombre_desconocido(self, svc):
        assert svc.resolve("Zorba") == "primera persona (Zorba narra)"

    def test_nombre_con_config_gender_femenino(self, svc):
        # El género explícito en storyteller_config sí cambia el output
        config = {"voice": {"person": "primera"}, "gender": "femenino"}
        assert svc.resolve("irene", storyteller_config=config) == "primera persona (ella narra)"

    def test_nombre_con_config_gender_masculino(self, svc):
        config = {"voice": {"person": "primera"}, "gender": "masculino"}
        assert svc.resolve("ricardo", storyteller_config=config) == "primera persona (él narra)"
