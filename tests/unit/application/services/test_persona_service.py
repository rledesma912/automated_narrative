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

    def test_nombre_femenino_irene(self, svc):
        assert svc.resolve("irene") == "primera persona (ella narra)"

    def test_nombre_femenino_case_insensitive(self, svc):
        assert svc.resolve("Irene") == "primera persona (ella narra)"

    def test_nombre_femenino_laura(self, svc):
        assert svc.resolve("laura") == "primera persona (ella narra)"

    def test_nombre_masculino_ricardo(self, svc):
        assert svc.resolve("ricardo") == "primera persona (él narra)"

    def test_nombre_masculino_juan(self, svc):
        assert svc.resolve("juan") == "primera persona (él narra)"

    def test_nombre_desconocido(self, svc):
        assert svc.resolve("Zorba") == "primera persona (Zorba narra)"
