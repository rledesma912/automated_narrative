"""Las entregas del tablero viven en disco (Spec-795 §2.1, §10.1).

Una entrega = una carpeta `AAAA-MM-DD-slug/` con `entrega.yaml` y sus archivos. Se leen en cada
pedido (publicar no reinicia nada). Una carpeta que no valida no rompe la página: queda en
`leer_todas()` como inválida, con su motivo. Solo se sirve lo que lista el `entrega.yaml`.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from pydantic import ValidationError

from src.application.services.tablero.config import tablero_config
from src.config import settings
from src.domain.tablero import Entrega
from src.messages import message

YAML = "entrega.yaml"
_ID = re.compile(r"^(\d{4}-\d{2}-\d{2})-[a-z0-9][a-z0-9-]*$")


class EntregaInvalidaError(ValueError):
    """La carpeta no es una entrega válida; el mensaje dice por qué."""


@dataclass(frozen=True)
class Invalida:
    id: str
    motivo: str


def carpeta_tablero() -> Path:
    """`settings.tablero_dir` o, vacío, `tablero/` al lado de la base (data/dev o data/prod)."""
    if settings.tablero_dir:
        return Path(settings.tablero_dir)
    return Path(settings.database_url.split("///", 1)[-1]).parent / "tablero"


def _nombre_valido(archivo: str) -> bool:
    return (
        bool(archivo) and not archivo.startswith(".") and "/" not in archivo and "\\" not in archivo
    )


def leer(carpeta: Path) -> Entrega:
    """Lee y valida una entrega; `EntregaInvalidaError` con el motivo si algo no está bien."""
    cfg = tablero_config()
    m = _ID.match(carpeta.name)
    if not m:
        raise EntregaInvalidaError(message("tablero.id_invalido", id=carpeta.name))
    ruta_yaml = carpeta / YAML
    if not ruta_yaml.is_file():
        raise EntregaInvalidaError(message("tablero.sin_yaml", id=carpeta.name))
    try:
        datos = yaml.safe_load(ruta_yaml.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise EntregaInvalidaError(message("tablero.yaml_roto", id=carpeta.name, error=e)) from e
    if not isinstance(datos, dict):
        raise EntregaInvalidaError(
            message("tablero.yaml_roto", id=carpeta.name, error=type(datos).__name__)
        )
    datos = {**datos, "id": carpeta.name}
    datos.setdefault("fecha", date.fromisoformat(m.group(1)))
    try:
        entrega = Entrega.model_validate(datos)
    except ValidationError as e:
        raise EntregaInvalidaError(message("tablero.yaml_roto", id=carpeta.name, error=e)) from e
    if not entrega.archivos():
        raise EntregaInvalidaError(message("tablero.sin_archivos", id=carpeta.name))
    tope = cfg.tope_mb_por_archivo * 2**20
    vistos: set[str] = set()
    for a in entrega.archivos():
        nombre = a.archivo
        if not _nombre_valido(nombre):
            raise EntregaInvalidaError(message("tablero.nombre_invalido", archivo=nombre))
        if nombre in vistos:
            raise EntregaInvalidaError(message("tablero.repetido", archivo=nombre))
        vistos.add(nombre)
        ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
        if ext not in cfg.extensiones:
            raise EntregaInvalidaError(message("tablero.extension", archivo=nombre))
        ruta = carpeta / nombre
        if not ruta.is_file():
            raise EntregaInvalidaError(message("tablero.falta_archivo", archivo=nombre))
        if ruta.stat().st_size > tope:
            raise EntregaInvalidaError(
                message("tablero.muy_grande", archivo=nombre, mb=cfg.tope_mb_por_archivo)
            )
    return entrega


def leer_todas(base: Path | None = None) -> tuple[list[Entrega], list[Invalida]]:
    """Todas las entregas, la más nueva primero, y las carpetas que no validan."""
    base = base or carpeta_tablero()
    entregas: list[Entrega] = []
    invalidas: list[Invalida] = []
    if not base.is_dir():
        return entregas, invalidas
    for carpeta in sorted(base.iterdir()):
        if not carpeta.is_dir() or carpeta.name.startswith("."):
            continue  # las temporales de publicar
        try:
            entregas.append(leer(carpeta))
        except EntregaInvalidaError as e:
            invalidas.append(Invalida(carpeta.name, str(e)))
    entregas.sort(key=lambda e: (e.fecha, e.id), reverse=True)
    return entregas, invalidas


def buscar(entrega_id: str, base: Path | None = None) -> Entrega | None:
    base = base or carpeta_tablero()
    if not _ID.match(entrega_id):
        return None
    carpeta = base / entrega_id
    if not carpeta.is_dir():
        return None
    try:
        return leer(carpeta)
    except EntregaInvalidaError:
        return None


def ruta_de(entrega: Entrega, archivo: str, base: Path | None = None) -> Path | None:
    """La ruta del archivo, solo si está declarado en el `entrega.yaml`."""
    if not entrega.tiene(archivo) or not _nombre_valido(archivo):
        return None
    return (base or carpeta_tablero()) / entrega.id / archivo


def publicar(origen: Path, base: Path, reemplazar: bool = False) -> Entrega:
    """Valida `origen` y lo copia a `base/<id>/` sin que la página vea una entrega a medias.

    Copia solo `entrega.yaml` y los archivos declarados, a una carpeta oculta, y la renombra.
    """
    entrega = leer(origen)
    destino = base / entrega.id
    if destino.exists() and not reemplazar:
        raise EntregaInvalidaError(message("tablero.ya_existe", id=entrega.id))
    base.mkdir(parents=True, exist_ok=True)
    tmp = base / f".{entrega.id}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    for nombre in [YAML, *(a.archivo for a in entrega.archivos())]:
        shutil.copy2(origen / nombre, tmp / nombre)
    viejo = base / f".{entrega.id}.old"
    if destino.exists():
        shutil.rmtree(viejo, ignore_errors=True)
        destino.rename(viejo)
    tmp.rename(destino)
    shutil.rmtree(viejo, ignore_errors=True)
    return entrega
