"""Spec-610: el paquete para el video (guion, la calabaza y el mapa de producción)."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel

from src.application.services import narrative_acts
from src.application.services.structure import DEFAULT_STRUCTURE
from src.application.services.video import pdf as video_pdf
from src.application.services.video import state as video_state
from src.application.services.video.config import estructura_del_relato, video_config
from src.application.services.video.files import slug
from src.domain.models import GeneratedNarrative
from src.domain.video import Mark, VideoScript
from src.infrastructure.database.repositories import (
    SQLGeneratedNarrativeRepository,
    SQLJobRepository,
    SQLVideoScriptRepository,
)
from src.messages import message

router = APIRouter(tags=["Video"])


@router.get("/video/lectura")
async def get_reading_settings(actos: int | None = None) -> dict:
    """Ritmo de lectura y largo del episodio (`config/video/lectura.yaml`): la web hace
    las mismas cuentas que el Core con estos valores. Spec-650: con `?actos=N` (los del
    relato), el episodio es el de su largo (el corto dura unos 7 minutos)."""
    lectura = video_config().lectura
    estructura = estructura_del_relato(actos) if actos else DEFAULT_STRUCTURE
    return {
        "palabras_por_minuto": lectura.palabras_por_minuto,
        "episodio_minutos": lectura.episodio(estructura).model_dump(),
        "estructura": estructura,
    }


# ── Lectura ──────────────────────────────────────────────────────────────────


async def _load(narrative_id: str) -> tuple[GeneratedNarrative, VideoScript]:
    try:
        nid = UUID(narrative_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de narrativa inválido")
    narrative = await SQLGeneratedNarrativeRepository().get_by_id(nid)
    script = await SQLVideoScriptRepository().get_by_narrative(nid) if narrative else None
    if script is None:
        raise HTTPException(status_code=404, detail=message("video.sin_paquete"))
    return narrative, script


def _view(narrative: GeneratedNarrative, script: VideoScript) -> dict:
    """El paquete con su estado frente al relato y las marcas reubicadas (no se guarda)."""
    acts = narrative_acts.split(narrative.content)
    data = script.model_dump(mode="json")
    lost = []
    for i, block in enumerate(script.bloques):
        tokens = video_state.block_tokens(acts, block.acto, block.desde, block.hasta)
        kept, gone = video_state.relocate(tokens, block.marcas)
        data["bloques"][i]["marcas"] = [m.model_dump() for m in kept]
        lost += [{"bloque": i + 1, "texto": t} for t in gone]
    data["estado"] = video_state.state(script, narrative.content).as_dict()
    data["marcas_perdidas"] = lost
    data["estilo_imagen"] = video_config().biblia.estilo
    data["transiciones"] = video_config().biblia.transiciones
    data["lectores"] = [lector.nombre for lector in video_config().lectores.lectores]
    data["cierre_fijo"] = video_config().presentador.cierre_fijo
    data["tipos"] = {k: v.model_dump() for k, v in video_config().biblia.tipos.items()}
    return data


@router.get("/generated-narratives/{narrative_id}/video-script")
async def get_video_script(narrative_id: str) -> dict:
    """El paquete de la variante (404 si todavía no se armó), con su estado."""
    narrative, script = await _load(narrative_id)
    return _view(narrative, script)


# ── Edición (Spec-610 T3.2) ──────────────────────────────────────────────────


class ReaderUpdate(BaseModel):
    lector: str | None


class BlockUpdate(BaseModel):
    indicacion: str | None = None
    pausa: Literal["ninguna", "corta", "larga"] | None = None
    marcas: list[tuple[int, int]] | None = None  # (desde_palabra, hasta_palabra)


class MomentUpdate(BaseModel):
    tipo: Literal["imagen", "animacion", "video"] | None = None
    que_se_ve: str | None = None
    lugar: str | None = None
    prompt_imagen: str | None = None
    prompt_movimiento: str | None = None
    transicion: str | None = None
    sonido: str | None = None


class PresenterUpdate(BaseModel):
    intro: str | None = None
    outro: str | None = None


async def _editable(narrative_id: str) -> tuple[GeneratedNarrative, VideoScript]:
    narrative, script = await _load(narrative_id)
    active = await SQLJobRepository().get_active_for_story(narrative.story_template_id)
    if active is not None:
        raise HTTPException(
            status_code=409,
            detail=message("api.ia_trabajando"),
            headers={"X-Job-Id": str(active.id)},
        )
    return narrative, script


def _index(items: list, number: int, key: str) -> int:
    if not 1 <= number <= len(items):
        raise HTTPException(
            status_code=404, detail=message(f"video.{key}_inexistente", numero=number)
        )
    return number - 1


@router.put("/generated-narratives/{narrative_id}/video-script/reader")
async def update_reader(narrative_id: str, body: ReaderUpdate) -> dict:
    _, script = await _editable(narrative_id)
    names = [lector.nombre for lector in video_config().lectores.lectores]
    if body.lector is not None and body.lector not in names:
        raise HTTPException(status_code=422, detail=message("video.lector_desconocido"))
    script.lector = body.lector
    await SQLVideoScriptRepository().save(script)
    return {"lector": script.lector}


@router.put("/generated-narratives/{narrative_id}/video-script/blocks/{number}")
async def update_block(narrative_id: str, number: int, body: BlockUpdate) -> dict:
    narrative, script = await _editable(narrative_id)
    i = _index(script.bloques, number, "bloque")
    block = script.bloques[i]
    if body.indicacion is not None:
        block.indicacion = body.indicacion.strip()
    if body.pausa is not None:
        block.pausa = body.pausa
    if body.marcas is not None:
        acts = narrative_acts.split(narrative.content)
        tokens = video_state.block_tokens(acts, block.acto, block.desde, block.hasta)
        block.marcas = _marks(tokens, body.marcas)
    await SQLVideoScriptRepository().save(script)
    return block.model_dump()


def _marks(tokens: list[str], spans: list[tuple[int, int]]) -> list[Mark]:
    """Las marcas pedidas, con su texto tomado del relato actual. Sin pisarse."""
    taken: set[int] = set()
    marks = []
    for start, end in sorted(spans):
        span = range(start, end + 1)
        if start < 0 or end < start or end >= len(tokens) or taken.intersection(span):
            raise HTTPException(status_code=422, detail=message("video.marca_invalida"))
        taken.update(span)
        marks.append(
            Mark(desde_palabra=start, hasta_palabra=end, texto=" ".join(tokens[start : end + 1]))
        )
    return marks


@router.put("/generated-narratives/{narrative_id}/video-script/moments/{number}")
async def update_moment(narrative_id: str, number: int, body: MomentUpdate) -> dict:
    _, script = await _editable(narrative_id)
    moment = script.momentos[_index(script.momentos, number, "momento")]
    if body.transicion is not None and body.transicion not in video_config().biblia.transiciones:
        raise HTTPException(status_code=422, detail=message("video.transicion_desconocida"))
    for name, value in body.model_dump(exclude_none=True).items():
        setattr(moment, name, value.strip() if isinstance(value, str) else value)
    await SQLVideoScriptRepository().save(script)
    return moment.model_dump()


@router.put("/generated-narratives/{narrative_id}/video-script/presenter")
async def update_presenter(narrative_id: str, body: PresenterUpdate) -> dict:
    _, script = await _editable(narrative_id)
    if body.intro is not None:
        script.calabaza.intro = body.intro.strip()
    if body.outro is not None:
        script.calabaza.outro = body.outro.strip()
    await SQLVideoScriptRepository().save(script)
    return script.calabaza.model_dump()


@router.get("/generated-narratives/{narrative_id}/video-script/calabaza.txt")
async def download_presenter_text(narrative_id: str) -> Response:
    """Spec-610 §3.3: la intro y el outro para pegar en ElevenLabs, rotulados aparte;
    el cierre fijo al final si está cargado (D18)."""
    narrative, script = await _load(narrative_id)
    parts = [
        message("video.txt_intro"),
        script.calabaza.intro,
        "",
        message("video.txt_outro"),
        script.calabaza.outro,
    ]
    cierre = video_config().presentador.cierre_fijo.strip()
    if cierre:
        parts += ["", message("video.txt_cierre"), cierre]
    name = f"calabaza-{slug(narrative.title, limit=60)}.txt"
    return Response(
        content="\n".join(parts) + "\n",
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


async def _pdf(narrative_id: str, template: str, build, prefix: str) -> Response:
    """Spec-610 §3.7.3–4: el PDF se arma al descargar con lo último guardado (D19)."""
    narrative, script = await _load(narrative_id)
    status = video_state.state(script, narrative.content)
    if status.estado == "cambiaron_parrafos":
        actos = ", ".join(str(n) for n in status.actos)
        raise HTTPException(
            status_code=409, detail=message("video.pdf_desactualizado", actos=actos)
        )
    title = narrative.title.split(" · ")[0]
    context = build(script, narrative.content, title, video_config())
    data = await run_in_threadpool(video_pdf.render_pdf, template, context)
    name = f"{prefix}-{slug(title, limit=60)}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/generated-narratives/{narrative_id}/video-script/guion.pdf")
async def download_reading_script(narrative_id: str) -> Response:
    return await _pdf(narrative_id, "guion.html.j2", video_pdf.guion_context, "guion")


@router.get("/generated-narratives/{narrative_id}/video-script/mapa.pdf")
async def download_production_map(narrative_id: str) -> Response:
    return await _pdf(narrative_id, "mapa.html.j2", video_pdf.mapa_context, "mapa")
