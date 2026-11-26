"""`python -m src tablero …` (Spec-795 §4): lo que usa Claude para publicar y leer opiniones.

`--env` elige `data/<env>/` (la carpeta y la base) sin tocar `DATABASE_URL`. Por defecto `dev`:
un error no publica en prod. Las opiniones de prod se leen con la base en solo lectura.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

from src.application.services.tablero.entregas import EntregaInvalidaError, leer_todas, publicar
from src.cli.exceptions import CLIError

DATA = Path("data")


def _base(env: str, data: Path = DATA) -> Path:
    return data / env / "tablero"


def cmd_publicar(origen: Path, env: str, reemplazar: bool, data: Path = DATA) -> str:
    if not origen.is_dir():
        raise CLIError(f"No existe la carpeta {origen}")
    try:
        e = publicar(origen, _base(env, data), reemplazar=reemplazar)
    except EntregaInvalidaError as err:
        raise CLIError(str(err)) from err
    return (
        f"Publicada «{e.titulo}» ({e.id}, {len(e.archivos())} archivos) en {env}: /tablero/{e.id}"
    )


def cmd_lista(env: str, data: Path = DATA) -> str:
    entregas, invalidas = leer_todas(_base(env, data))
    lineas = [f"{e.fecha}  {e.proyecto:<12} {e.id}  «{e.titulo}»" for e in entregas]
    lineas += [f"INVÁLIDA  {m.id}: {m.motivo}" for m in invalidas]
    return "\n".join(lineas) or "(el tablero está vacío)"


def cmd_opiniones(env: str, entrega: str | None, desde: str | None, data: Path = DATA) -> str:
    db = data / env / "stories.db"
    if not db.is_file():
        raise CLIError(f"No existe la base {db}")
    sql = "SELECT entrega, archivo, tipo, texto, created_at FROM tablero_opinion WHERE 1=1"
    args: list[str] = []
    if entrega:
        sql += " AND entrega = ?"
        args.append(entrega)
    if desde:
        sql += " AND created_at >= ?"
        args.append(desde)
    sql += " ORDER BY entrega, archivo, id"
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        filas = conn.execute(sql, args).fetchall()
    except sqlite3.OperationalError:
        filas = []  # base sin la tabla (todavía sin deploy): no hay opiniones
    finally:
        conn.close()
    if not filas:
        return "(sin opiniones)"
    por: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
    for ent, arch, tipo, texto, creada in filas:
        por[(ent, arch)].append((tipo, texto, creada))
    salida: list[str] = []
    actual = None
    for (ent, arch), ops in por.items():
        if ent != actual:
            salida.append(f"\n## {ent}")
            actual = ent
        si = sum(t == "me_gusta" for t, _, _ in ops)
        no = sum(t == "no_va" for t, _, _ in ops)
        salida.append(f"- {arch}: me gusta {si} · no va {no}")
        salida += [f"    nota ({c[:16]}): {x}" for t, x, c in ops if t == "nota"]
    return "\n".join(salida).strip()
