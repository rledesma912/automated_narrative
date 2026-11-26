"""API del tablero (Spec-795 §3).

- `GET /tablero/entregas?proyecto=`: las entregas (la más nueva primero) y los proyectos que hay.
- `GET /tablero/entregas/{id}`: la entrega con sus filas, sus archivos sueltos y las opiniones.
- `GET /tablero/entregas/{id}/archivos/{archivo}`: el archivo, solo si está en el `entrega.yaml`.
- `POST /tablero/entregas/{id}/opiniones` y `DELETE /tablero/opiniones/{id}`: opinar y sacar.
- `GET /tablero/invalidas`: las carpetas que no validan, con su motivo (para /debug).
"""

from __future__ import annotations

import asyncio
import mimetypes
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.application.services.tablero import entregas as svc
from src.application.services.tablero.config import tablero_config
from src.domain.tablero import Archivo, Entrega, Opinion, TipoOpinion, tipo_medio
from src.infrastructure.database.repositories import SQLTableroRepository
from src.messages import message

router = APIRouter(tags=["tablero"])

MINIATURAS_EN_LISTA = 4


class OpinionNueva(BaseModel):
    archivo: str
    tipo: TipoOpinion
    texto: str = Field("", max_length=2000)


def _url(entrega_id: str, archivo: str) -> str:
    return f"/api/v1/tablero/entregas/{quote(entrega_id)}/archivos/{quote(archivo)}"


def _archivo(e: Entrega, a: Archivo, opiniones: list[Opinion] | None = None) -> dict:
    vista: dict = {
        "archivo": a.archivo,
        "leyenda": a.leyenda,
        "url": _url(e.id, a.archivo),
        "tipo_medio": tipo_medio(a.archivo),
    }
    if opiniones is not None:
        mias = [o for o in opiniones if o.archivo == a.archivo]
        vista["me_gusta"] = sum(o.tipo == "me_gusta" for o in mias)
        vista["no_va"] = sum(o.tipo == "no_va" for o in mias)
        vista["opiniones"] = [
            o.model_dump(mode="json", exclude={"entrega", "archivo"}) for o in mias
        ]
    return vista


def _cabecera(e: Entrega) -> dict:
    return {
        "id": e.id,
        "titulo": e.titulo,
        "proyecto": e.proyecto,
        "proyecto_nombre": tablero_config().nombre_de(e.proyecto),
        "fecha": e.fecha.isoformat(),
        "que_mirar": e.que_mirar,
    }


async def _entrega_or_404(entrega_id: str) -> Entrega:
    e = await asyncio.to_thread(svc.buscar, entrega_id)
    if e is None:
        raise HTTPException(status_code=404, detail=message("tablero.no_encontrada"))
    return e


@router.get("/tablero/entregas")
async def listar(proyecto: str | None = None) -> dict:
    todas, _ = await asyncio.to_thread(svc.leer_todas)
    cuentas = await SQLTableroRepository().cuentas()
    cfg = tablero_config()
    slugs = {e.proyecto for e in todas}
    orden = [p for p in cfg.proyectos if p in slugs] + sorted(slugs - set(cfg.proyectos))
    elegidas = [e for e in todas if not proyecto or e.proyecto == proyecto]
    return {
        "proyectos": [{"slug": p, "nombre": cfg.nombre_de(p)} for p in orden],
        "entregas": [
            {
                **_cabecera(e),
                "archivos": [_archivo(e, a) for a in e.archivos()[:MINIATURAS_EN_LISTA]],
                "total_archivos": len(e.archivos()),
                "opiniones": cuentas[e.id],
            }
            for e in elegidas
        ],
    }


@router.get("/tablero/invalidas")
async def invalidas() -> list[dict]:
    _, malas = await asyncio.to_thread(svc.leer_todas)
    return [{"id": m.id, "motivo": m.motivo} for m in malas]


@router.get("/tablero/entregas/{entrega_id}")
async def ver(entrega_id: str) -> dict:
    e = await _entrega_or_404(entrega_id)
    opiniones = await SQLTableroRepository().de_entrega(e.id)
    return {
        **_cabecera(e),
        "filas": [
            {"titulo": f.titulo, "archivos": [_archivo(e, a, opiniones) for a in f.imagenes]}
            for f in e.filas
        ],
        "sueltas": [_archivo(e, a, opiniones) for a in e.imagenes],
    }


@router.get("/tablero/entregas/{entrega_id}/archivos/{archivo}")
async def archivo(entrega_id: str, archivo: str) -> FileResponse:
    e = await _entrega_or_404(entrega_id)
    ruta = svc.ruta_de(e, archivo)
    if ruta is None or not ruta.is_file():
        raise HTTPException(status_code=404, detail=message("tablero.archivo_no_encontrado"))
    headers = {"Cache-Control": "no-store"}
    if archivo.lower().endswith(".svg"):
        # Un SVG puede traer <script>: que el navegador no lo corra.
        headers["Content-Security-Policy"] = "script-src 'none'"
    media = mimetypes.guess_type(archivo)[0] or "application/octet-stream"
    return FileResponse(ruta, media_type=media, headers=headers)


@router.post("/tablero/entregas/{entrega_id}/opiniones", status_code=201)
async def opinar(entrega_id: str, body: OpinionNueva) -> dict:
    e = await _entrega_or_404(entrega_id)
    if not e.tiene(body.archivo):
        raise HTTPException(status_code=422, detail=message("tablero.archivo_no_encontrado"))
    texto = body.texto.strip() if body.tipo == "nota" else ""
    if body.tipo == "nota" and not texto:
        raise HTTPException(status_code=422, detail=message("tablero.nota_vacia"))
    o = await SQLTableroRepository().agregar(e.id, body.archivo, body.tipo, texto)
    return o.model_dump(mode="json")


@router.delete("/tablero/opiniones/{opinion_id}", status_code=204)
async def sacar(opinion_id: int) -> None:
    if not await SQLTableroRepository().borrar(opinion_id):
        raise HTTPException(status_code=404, detail=message("tablero.opinion_no_encontrada"))
