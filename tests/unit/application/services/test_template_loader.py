"""Tests para TemplateLoader — Spec 063 Slice B."""

from pathlib import Path

import pytest

from src.application.services.template_loader import TemplateLoader


@pytest.fixture
def loader(tmp_path: Path) -> TemplateLoader:
    return TemplateLoader(tmp_path)


def _write(tmp_path: Path, name: str, content: str) -> None:
    (tmp_path / name).write_text(content, encoding="utf-8")


class TestTemplateLoaderLoad:
    def test_carga_archivo_existente(self, loader, tmp_path):
        _write(tmp_path, "foo.md", "hola mundo")
        assert loader.load("foo.md") == "hola mundo"

    def test_retorna_vacio_si_no_existe(self, loader):
        assert loader.load("no_existe.md") == ""

    def test_cacheo_no_relee_disco(self, loader, tmp_path):
        _write(tmp_path, "cached.md", "v1")
        loader.load("cached.md")
        (tmp_path / "cached.md").write_text("v2", encoding="utf-8")
        assert loader.load("cached.md") == "v1"

    def test_strip_contenido(self, loader, tmp_path):
        _write(tmp_path, "space.md", "  contenido  \n")
        assert loader.load("space.md") == "contenido"


class TestTemplateLoaderFragment:
    """Spec-620: secciones del prompt en `fragments/<rol>/<seccion>.md`."""

    def _fragment(self, tmp_path: Path, name: str, content: str) -> None:
        path = tmp_path / "fragments" / f"{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_formatea_con_los_datos(self, loader, tmp_path):
        self._fragment(tmp_path, "voz/como_esta", "CÓMO ESTÁ {narrador} AHORA: {estado}\n")
        assert loader.fragment("voz/como_esta", narrador="JOSÉ", estado="cansado") == (
            "CÓMO ESTÁ JOSÉ AHORA: cansado"
        )

    def test_quita_solo_el_ultimo_salto_de_linea(self, loader, tmp_path):
        """Una línea en blanco al final del archivo es un `\\n` que la sección necesita."""
        self._fragment(tmp_path, "voz/bloque", "  TÍTULO:\n{texto}\n\n")
        assert loader.fragment("voz/bloque", texto="algo") == "  TÍTULO:\nalgo\n"

    def test_cachea_el_archivo_y_formatea_cada_vez(self, loader, tmp_path):
        self._fragment(tmp_path, "voz/x", "{a}\n")
        assert loader.fragment("voz/x", a="1") == "1"
        (tmp_path / "fragments" / "voz" / "x.md").write_text("otro {a}\n", encoding="utf-8")
        assert loader.fragment("voz/x", a="2") == "2"

    def test_fragmento_inexistente_es_error(self, loader):
        with pytest.raises(FileNotFoundError, match="voz/no_existe"):
            loader.fragment("voz/no_existe")

    def test_dato_faltante_es_error(self, loader, tmp_path):
        self._fragment(tmp_path, "voz/x", "{narrador}\n")
        with pytest.raises(KeyError, match="narrador"):
            loader.fragment("voz/x")
