"""Spec-795 §4: los comandos del tablero contra un data/ temporal."""

import sqlite3

import pytest

from src.cli import tablero
from src.cli.exceptions import CLIError
from tests.support.tablero import entrega


def test_publicar_y_lista(tmp_path):
    data = tmp_path / "data"
    origen = entrega(tmp_path / "origen")
    salida = tablero.cmd_publicar(origen, "dev", False, data)
    assert "/tablero/2026-11-26-calabaza-hoja" in salida
    assert (data / "dev" / "tablero" / origen.name / "a.png").is_file()
    assert not (data / "prod").exists()  # por defecto, dev
    assert "calabaza" in tablero.cmd_lista("dev", data)
    with pytest.raises(CLIError, match="--reemplazar"):
        tablero.cmd_publicar(origen, "dev", False, data)


def test_opiniones_en_texto(tmp_path):
    db = tmp_path / "data" / "prod" / "stories.db"
    db.parent.mkdir(parents=True)
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE tablero_opinion (id INTEGER PRIMARY KEY, entrega TEXT, archivo TEXT,"
        " tipo TEXT, texto TEXT, created_at TEXT)"
    )
    conn.executemany(
        "INSERT INTO tablero_opinion (entrega, archivo, tipo, texto, created_at) VALUES (?,?,?,?,?)",
        [
            ("e1", "a.png", "me_gusta", "", "2026-11-26T10:00:00"),
            ("e1", "a.png", "nota", "más oscura", "2026-11-26T10:01:00"),
            ("e1", "b.png", "no_va", "", "2026-11-20T10:00:00"),
        ],
    )
    conn.commit()
    conn.close()
    texto = tablero.cmd_opiniones("prod", None, None, tmp_path / "data")
    assert "- a.png: me gusta 1 · no va 0" in texto and "más oscura" in texto
    nuevo = tablero.cmd_opiniones("prod", None, "2026-11-25", tmp_path / "data")
    assert "b.png" not in nuevo


def test_opiniones_sin_tabla(tmp_path):
    db = tmp_path / "data" / "prod" / "stories.db"
    db.parent.mkdir(parents=True)
    sqlite3.connect(db).close()
    assert tablero.cmd_opiniones("prod", None, None, tmp_path / "data") == "(sin opiniones)"
