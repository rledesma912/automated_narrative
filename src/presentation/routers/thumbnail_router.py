"""API de las miniaturas (Spec-790 §10.7).

- `GET /stories/{id}/thumbnail`: lo cargado (con lo que propone la historia si está vacío), las
  piezas, las tandas, el tono que propone el lugar y el catálogo de tonos.
- `PUT /stories/{id}/thumbnail`: guarda los campos (autoguardado). Si cambian el color o el
  tono y hay una tanda, la recolorea sin GPU.
- `POST /stories/{id}/thumbnail/sketches/{personaje|escenario}`: sube un boceto (PNG o JPG).
- `GET /stories/{id}/thumbnail/sketches/{tipo}.png` y `…/images/{tanda}/{plantilla}.jpg`.
"""

from __future__ import annotations

import asyncio
import io
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel

from src.application.services.miniatura.arnes import carpeta_de, recolorear
from src.application.services.miniatura.arte import arte
from src.domain.thumbnail import Color, Figura, Thumbnail, ThumbnailInput
from src.infrastructure.database.repositories import (
    SQLJobRepository,
    SQLStoryRepository,
    SQLThumbnailRepository,
)
from src.messages import message
from src.presentation import thumbnail_jobs

router = APIRouter(tags=["thumbnail"])

MAX_BOCETO = 20 * 2**20


class ThumbnailUpdate(BaseModel):
    figure: Figura | None = None
    figure_description: str | None = None
    place_description: str | None = None
    color: Color | None = None
    tone: str | None = None


async def _story_or_404(story_id: str):
    try:
        story = await SQLStoryRepository().get_by_id(UUID(story_id))
    except ValueError:
        story = None
    if story is None:
        raise HTTPException(
            status_code=404, detail=message("miniatura.historia_no_encontrada", story_id=story_id)
        )
    return story


def _propuesta(story) -> ThumbnailInput:
    """Sin nada cargado: la entidad (si la hay) y el primer lugar de la historia (Spec-710)."""
    entidad = story.entities[0] if getattr(story, "entities", None) else None
    figura = "entidad" if entidad else "protagonista"
    desc = ""
    if entidad:
        desc = " ".join(x for x in (entidad.description, entidad.manifestations) if x).strip()
    lugar = ""
    if getattr(story, "scenarios", None):
        s = story.scenarios[0]
        lugar = " ".join(x for x in (s.name, s.description) if x).strip()
    return ThumbnailInput(figure=figura, figure_description=desc, place_description=lugar)


async def _thumb(story) -> Thumbnail:
    repo = SQLThumbnailRepository()
    thumb = await repo.get(story.id)
    if thumb is None:
        thumb = Thumbnail(story_id=str(story.id), input=_propuesta(story))
    return thumb


def _vista(thumb: Thumbnail) -> dict:
    a = arte()
    data = thumb.model_dump(mode="json")
    data["tono_propuesto"] = a.tono_del_lugar(thumb.input.place_description)
    data["tono_efectivo"] = a.tono_valido(thumb.input.tone, thumb.input.place_description)
    data["tonos"] = [{"id": k, "nombre": t.nombre} for k, t in a.tonos.items()]
    data["plantillas"] = [{"id": k, "nombre": p.nombre} for k, p in a.plantillas.items()]
    return data


async def _comfy_disponible() -> bool:
    """§2.6: si la compu que hace las imágenes no responde, la página lo avisa antes."""
    try:
        await asyncio.wait_for(thumbnail_jobs.comfy_client().vram_libre_mb(), timeout=3)
        return True
    except Exception:  # noqa: BLE001 — apagada, sin red o respuesta rara: no está disponible
        return False


@router.get("/stories/{story_id}/thumbnail")
async def get_thumbnail(story_id: str):
    story = await _story_or_404(story_id)
    vista = _vista(await _thumb(story))
    vista["comfy_disponible"] = await _comfy_disponible()
    return vista


@router.put("/stories/{story_id}/thumbnail")
async def put_thumbnail(story_id: str, body: ThumbnailUpdate):
    story = await _story_or_404(story_id)
    thumb = await _thumb(story)
    antes = (thumb.input.color, thumb.input.tone, thumb.input.place_description)
    cambios = body.model_dump(exclude_none=True)
    thumb.input = thumb.input.model_copy(update=cambios)
    if (
        antes != (thumb.input.color, thumb.input.tone, thumb.input.place_description)
        and thumb.last_batch
    ):
        if await SQLJobRepository().get_active_for_story(story.id) is None:
            recolorear(thumb, carpeta_de(str(story.id)))
    await SQLThumbnailRepository().save(thumb)
    return _vista(thumb)


@router.post("/stories/{story_id}/thumbnail/sketches/{tipo}")
async def upload_sketch(
    story_id: str, tipo: Literal["personaje", "escenario"], file: UploadFile = File(...)
):
    story = await _story_or_404(story_id)
    datos = await file.read()
    if len(datos) > MAX_BOCETO:
        raise HTTPException(status_code=422, detail=message("miniatura.boceto_invalido"))
    try:
        im = Image.open(io.BytesIO(datos))
        im.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=422, detail=message("miniatura.boceto_invalido")) from None
    thumb = await _thumb(story)
    carpeta = carpeta_de(str(story.id))
    (carpeta / "bocetos").mkdir(parents=True, exist_ok=True)
    nombre = f"bocetos/{tipo}.png"
    im.convert("RGB").save(carpeta / nombre)
    if tipo == "personaje":
        thumb.input.character_sketch = nombre
    else:
        thumb.input.scene_sketch = nombre
    await SQLThumbnailRepository().save(thumb)
    return _vista(thumb)


@router.get("/stories/{story_id}/thumbnail/sketches/{tipo}.png")
async def get_sketch(story_id: str, tipo: Literal["personaje", "escenario"]):
    ruta = carpeta_de(story_id) / "bocetos" / f"{tipo}.png"
    if not ruta.exists():
        raise HTTPException(status_code=404, detail=message("miniatura.no_existe"))
    return FileResponse(ruta, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.get("/stories/{story_id}/thumbnail/images/{tanda}/{plantilla}.jpg")
async def get_image(story_id: str, tanda: int, plantilla: str):
    if plantilla not in arte().plantillas:
        raise HTTPException(status_code=404, detail=message("miniatura.no_existe"))
    ruta = carpeta_de(story_id) / f"tanda_{tanda}" / f"{plantilla}.jpg"
    if not ruta.exists():
        raise HTTPException(status_code=404, detail=message("miniatura.no_existe"))
    return FileResponse(ruta, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/thumbnails")
async def list_thumbnails():
    """Las historias que ya tienen miniatura (para el chip de la lista)."""
    repo = SQLThumbnailRepository()
    return {"story_ids": sorted(await repo.story_ids())}
