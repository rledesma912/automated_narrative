"""Tests para SynopsisSliceResolver — Spec 063 Slice C."""

import pytest

from src.application.services.synopsis_slice_resolver import SynopsisSliceResolver

SINOPSIS_LARGA = "\n\n".join([f"Párrafo {i}." for i in range(1, 7)])  # 6 párrafos


@pytest.fixture
def resolver() -> SynopsisSliceResolver:
    return SynopsisSliceResolver()


class TestResolveStrategy:

    def test_strategy_none_retorna_vacio(self, resolver):
        assert resolver.resolve("algo", 1, 5, "none") == ""

    def test_strategy_full_retorna_todo(self, resolver):
        s = "sinopsis completa"
        assert resolver.resolve(s, 1, 5, "full") == s

    def test_strategy_beat_slice_llama_get_slice(self, resolver):
        sinopsis = "A.\n\nB.\n\nC.\n\nD.\n\nE."
        result = resolver.resolve(sinopsis, 1, 5, "beat_slice")
        assert "A." in result

    def test_strategy_desconocida_usa_beat_slice(self, resolver):
        sinopsis = "A.\n\nB.\n\nC.\n\nD.\n\nE."
        result = resolver.resolve(sinopsis, 1, 5, "desconocida")
        assert isinstance(result, str)


class TestGetSlice:

    def test_sinopsis_corta_retorna_dos_oraciones(self, resolver):
        sinopsis = "Primera oración. Segunda oración. Tercera oración."
        result = resolver.get_slice(sinopsis, 1, 5)
        assert result == "Primera oración. Segunda oración."

    def test_sinopsis_larga_beat_1(self, resolver):
        result = resolver.get_slice(SINOPSIS_LARGA, 1, 5)
        assert "Párrafo 1" in result

    def test_sinopsis_larga_beat_5(self, resolver):
        result = resolver.get_slice(SINOPSIS_LARGA, 5, 5)
        assert "Párrafo 6" in result or "Párrafo 5" in result

    def test_sinopsis_exactamente_igual_a_beats(self, resolver):
        sinopsis = "A.\n\nB.\n\nC.\n\nD.\n\nE."
        for i in range(1, 6):
            result = resolver.get_slice(sinopsis, i, 5)
            assert result  # cada beat obtiene algo

    def test_sinopsis_vacia_retorna_vacio(self, resolver):
        result = resolver.get_slice("", 1, 5)
        assert result == ""

    def test_todos_los_beats_obtienen_contenido(self, resolver):
        # 10 párrafos únicos, 5 beats — cada beat debe obtener algo
        labels = [f"PARRAFO_ALFA_{c}" for c in "ABCDEFGHIJ"]
        sinopsis = "\n\n".join(labels)
        slices = [resolver.get_slice(sinopsis, i, 5) for i in range(1, 6)]
        assert all(s.strip() for s in slices), "Algún beat recibió slice vacío"
