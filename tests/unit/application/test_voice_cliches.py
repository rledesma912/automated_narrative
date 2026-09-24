"""Spec-470 T0.1: lista de clichés de la Voz."""

from src.application.services.voice_cliches import load_cliches


def test_lista_del_repo():
    cliches = load_cliches()
    assert "me heló la sangre" in cliches
    assert not any(c.startswith("#") for c in cliches)


def test_ignora_comentarios_vacios_y_duplicados(tmp_path):
    f = tmp_path / "c.txt"
    f.write_text("# comentario\n\nMe Heló La Sangre\nme heló la sangre\n  escalofrío  \n", "utf-8")
    assert load_cliches(f) == ["me heló la sangre", "escalofrío"]


def test_sin_archivo_lista_vacia(tmp_path):
    assert load_cliches(tmp_path / "no.txt") == []
