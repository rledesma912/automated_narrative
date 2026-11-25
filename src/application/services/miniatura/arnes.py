"""El arnés de las miniaturas (Spec-790 D15, §10.7): Python ordena, ComfyUI hace una cosa por vez.

  textos      la IA separa lo que escribió Yael: personaje solo, lugar vacío y relación (T3.3)
  personaje   boceto → `boceto_a_imagen` (prompts/personaje.md) → `recortar` → PNG con alfa
  escenario   boceto → `boceto_a_imagen` (prompts/escenario.md) → curva en Python →
              `foto_img2img` (prompts/fotografiar_escenario.md) → `recortar` (lo importante)
  4 opciones  por plantilla: ubicar → espejar si tapa lo importante → oscurecer la figura →
              componer → `boceto_a_imagen` sobre la zona (prompts/fundir.md) → igualar y pegar
              con máscara → color (tono del lugar, Halloween o blanco y negro) → JPG

El personaje y el escenario se reusan mientras no cambien su boceto ni su descripción (hash).
La composición sin color y el alfa de cada opción quedan guardados: cambiar el color o el tono
no vuelve a usar la GPU (`recolorear`).
"""

from __future__ import annotations

import asyncio
import hashlib
import random
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from src.application.services.miniatura import imagen as im_
from src.application.services.miniatura import textos as textos_
from src.application.services.miniatura.arte import Arte, prompt
from src.application.services.miniatura.arte import arte as cargar_arte
from src.config import settings
from src.domain.interfaces import LLMProvider
from src.domain.jobs import JobStage
from src.domain.thumbnail import Batch, ImageTexts, Part, Thumbnail, ThumbnailImage
from src.infrastructure.adapters.comfy.client import ComfyError, ComfyPort
from src.messages import message

VRAM_NECESARIA_MB = 9500  # Qwen-Edit 2511: ~10,5 GB de pico en la 3060 de 12 (E1, E4)
ESPERA_GPU_S = 30 * 60
CADA_S = 15


def carpeta_de(story_id: str) -> Path:
    if settings.miniaturas_dir:
        base = Path(settings.miniaturas_dir)
    else:
        raw = settings.database_url.split("///", 1)[-1]
        base = Path(raw).parent / "miniaturas"
    return base / str(story_id)


@dataclass
class Etapa:
    stage: JobStage
    beat: int | None = None
    total: int | None = None


def _hash(*partes: bytes | str) -> str:
    h = hashlib.sha256()
    for p in partes:
        h.update(p if isinstance(p, bytes) else p.encode("utf-8"))
    return h.hexdigest()[:16]


def validar(thumb: Thumbnail, carpeta: Path) -> None:
    i = thumb.input
    if not i.character_sketch or not (carpeta / i.character_sketch).exists():
        raise ValueError(message("miniatura.falta_boceto_personaje"))
    if not i.scene_sketch or not (carpeta / i.scene_sketch).exists():
        raise ValueError(message("miniatura.falta_boceto_escenario"))
    if not i.figure_description.strip():
        raise ValueError(message("miniatura.falta_como_es"))


class Arnes:
    def __init__(
        self,
        comfy: ComfyPort,
        carpeta: Path,
        arte: Arte | None = None,
        llm: LLMProvider | None = None,
    ):
        self.comfy = comfy
        self.carpeta = carpeta
        self.arte = arte or cargar_arte()
        self.llm = llm

    # ── los textos (T3.3) ────────────────────────────────────────────────────────
    async def textos(self, thumb: Thumbnail) -> ImageTexts:
        """Lo que la IA separó de las descripciones; se reusa mientras no cambien. Sin IA (los
        spikes) van las descripciones tal cual."""
        i = thumb.input
        h = _hash(i.figure_description, i.place_description, "textos-v1")
        if thumb.texts and thumb.texts.input_hash == h:
            return thumb.texts
        if self.llm is None:
            return ImageTexts(
                personaje=i.figure_description, escenario=i.place_description, input_hash=h
            )
        thumb.texts = await textos_.separar(self.llm, i, h)
        return thumb.texts

    # ── la GPU por turnos (D10) ──────────────────────────────────────────────────
    async def esperar_gpu(self) -> AsyncIterator[Etapa]:
        await self.comfy.liberar()
        inicio = time.monotonic()
        avisado = False
        while await self.comfy.vram_libre_mb() < VRAM_NECESARIA_MB:
            if not avisado:
                avisado = True
                yield Etapa(JobStage.ESPERANDO_GPU)
            if time.monotonic() - inicio > ESPERA_GPU_S:
                raise ComfyError(message("miniatura.gpu_ocupada"))
            await asyncio.sleep(CADA_S)
            await self.comfy.liberar()  # ComfyUI descarga sus modelos recién cuando queda libre

    # ── las piezas ───────────────────────────────────────────────────────────────
    async def personaje(self, thumb: Thumbnail, semilla: int, desc: str) -> Path:
        i = thumb.input
        boceto = self.carpeta / i.character_sketch
        cambio = self.arte.personaje.cambio_foto
        h = _hash(
            boceto.read_bytes(),
            prompt("personaje", desc),
            prompt("fotografiar_personaje", desc),
            f"personaje-v2-{cambio}",
        )
        previo = thumb.parts.get("personaje")
        if previo and previo.input_hash == h and (self.carpeta / previo.file).exists():
            return self.carpeta / previo.file
        t0 = time.monotonic()
        piezas = self.carpeta / "piezas"
        qwen = await self.comfy.correr(
            "boceto_a_imagen",
            {"prompt": prompt("personaje", desc), "semilla": semilla},
            {"boceto": boceto},
            piezas / "personaje_qwen.png",
        )
        # E11: Qwen respeta el boceto pero lo deja como render; Z-Image lo vuelve foto.
        crudo = await self.comfy.correr(
            "foto_img2img",
            {
                "prompt": prompt("fotografiar_personaje", desc),
                "semilla": semilla,
                "cambio": cambio,
            },
            {"imagen": qwen},
            piezas / "personaje_crudo.png",
        )
        mascara = await self.comfy.correr(
            "recortar", {}, {"imagen": crudo}, self.carpeta / "piezas" / "personaje_mascara.png"
        )
        destino = self.carpeta / "piezas" / "personaje.png"
        im_.con_alfa(Image.open(crudo), Image.open(mascara)).save(destino)
        thumb.parts["personaje"] = Part(
            file=str(destino.relative_to(self.carpeta)),
            input_hash=h,
            seconds=round(time.monotonic() - t0, 1),
        )
        return destino

    async def escenario(self, thumb: Thumbnail, semilla: int, desc: str) -> tuple[Path, Path]:
        i = thumb.input
        boceto = self.carpeta / i.scene_sketch
        h = _hash(
            boceto.read_bytes(),
            prompt("escenario", desc),
            prompt("fotografiar_escenario", desc),
            "escenario-v1",
        )
        previo, imp = thumb.parts.get("escenario"), thumb.parts.get("importante")
        if (
            previo
            and imp
            and previo.input_hash == h
            and (self.carpeta / previo.file).exists()
            and (self.carpeta / imp.file).exists()
        ):
            return self.carpeta / previo.file, self.carpeta / imp.file
        t0 = time.monotonic()
        piezas = self.carpeta / "piezas"
        qwen = await self.comfy.correr(
            "boceto_a_imagen",
            {"prompt": prompt("escenario", desc), "semilla": semilla},
            {"boceto": boceto},
            piezas / "escenario_crudo.png",
        )
        oscuro = piezas / "escenario_oscurecido.png"
        im_.oscurecer_escenario(Image.open(qwen), self.arte).save(oscuro)
        foto = await self.comfy.correr(
            "foto_img2img",
            {
                "prompt": prompt("fotografiar_escenario", desc),
                "semilla": semilla,
                "cambio": self.arte.escenario.cambio_foto,
            },
            {"imagen": oscuro},
            piezas / "escenario.png",
        )
        en_lienzo = piezas / "escenario_lienzo.png"
        im_.lienzo(Image.open(foto), self.arte).save(en_lienzo)
        importante = await self.comfy.correr(
            "recortar", {}, {"imagen": en_lienzo}, piezas / "importante.png"
        )
        thumb.parts["escenario"] = Part(
            file=str(foto.relative_to(self.carpeta)),
            input_hash=h,
            seconds=round(time.monotonic() - t0, 1),
        )
        thumb.parts["importante"] = Part(
            file=str(importante.relative_to(self.carpeta)), input_hash=h
        )
        return foto, importante

    # ── la tanda ─────────────────────────────────────────────────────────────────
    async def armar(self, thumb: Thumbnail) -> AsyncIterator[Etapa | Batch]:
        """Arma una tanda de 4. Va avisando las etapas y al final entrega la tanda."""
        validar(thumb, self.carpeta)
        t0 = time.monotonic()
        txt = await self.textos(thumb)  # antes de la GPU: si la IA no atiende, falla ya
        async for e in self.esperar_gpu():
            yield e
        semilla_piezas = (
            int(_hash(thumb.story_id), 16) % 1_000_000
        )  # la misma mientras no cambie nada
        yield Etapa(JobStage.PERSONAJE)
        fig_path = await self.personaje(thumb, semilla_piezas, txt.personaje)
        yield Etapa(JobStage.ESCENARIO)
        esc_path, imp_path = await self.escenario(thumb, semilla_piezas, txt.escenario)

        n = (thumb.last_batch.n + 1) if thumb.last_batch else 1
        semilla = random.randint(1, 1_000_000)
        i = thumb.input
        tono = self.arte.tono_valido(i.tone, i.place_description)
        carpeta_tanda = self.carpeta / f"tanda_{n}"
        carpeta_tanda.mkdir(parents=True, exist_ok=True)
        figura = Image.open(fig_path).convert("RGBA")
        apoyo = im_.apoyo(figura)
        escenario = Image.open(esc_path)
        importante = Image.open(imp_path)
        batch = Batch(n=n, seed=semilla, color=i.color, tone=tono)
        total = len(self.arte.plantillas)
        for k, (clave, p) in enumerate(self.arte.plantillas.items(), start=1):
            yield Etapa(JobStage.COMPONIENDO, k, total)
            f, pos = im_.ubicar(im_.figura_recortada(figura, p.recorte), p, apoyo, self.arte)
            alfa = im_.alfa_en_cuadro(f, pos, self.arte)
            espejo = im_.espejo_conviene(alfa, importante)
            fondo = im_.lienzo(escenario, self.arte, espejo)
            f2 = im_.oscurecer_figura(f, fondo, alfa, self.arte)
            comp = im_.componer(fondo, f2, pos, apoyo, p, self.arte)
            m = im_.mascara_fundir(alfa, self.arte)
            caja = im_.zona(m, self.arte)
            zona_png = carpeta_tanda / f"{clave}_zona.png"
            comp.crop(caja).save(zona_png)
            editado = await self.comfy.correr(
                "boceto_a_imagen",
                {"prompt": prompt("fundir"), "semilla": semilla + k},
                {"boceto": zona_png},
                carpeta_tanda / f"{clave}_fundido.png",
            )
            final = im_.pegar_fundido(comp, Image.open(editado), caja, m, self.arte)
            final = im_.restaurar_luces(comp, final)  # T6.4: el fundido les cambiaba el tono
            if p.recorte == 1:
                final = im_.a_medio_ver(final, fondo, alfa, txt.a_medio_ver, self.arte)
            final.save(carpeta_tanda / f"{clave}_sin_color.png")
            alfa.save(carpeta_tanda / f"{clave}_alfa.png")
            jpg = carpeta_tanda / f"{clave}.jpg"
            im_.colorear(final, alfa, i.color, tono, self.arte).save(
                jpg, quality=self.arte.lienzo.calidad_jpg
            )
            batch.images.append(
                ThumbnailImage(template=clave, file=str(jpg.relative_to(self.carpeta)))
            )
        await self.comfy.liberar()
        batch.seconds = round(time.monotonic() - t0, 1)
        yield batch


def recolorear(thumb: Thumbnail, carpeta: Path, arte: Arte | None = None) -> Batch | None:
    """Cambia el color o el tono de la última tanda sin GPU (~1 s por imagen)."""
    a = arte or cargar_arte()
    batch = thumb.last_batch
    if batch is None:
        return None
    i = thumb.input
    tono = a.tono_valido(i.tone, i.place_description)
    for img in batch.images:
        base = carpeta / Path(img.file).with_suffix("")
        sin_color = base.parent / f"{base.name}_sin_color.png"
        alfa = base.parent / f"{base.name}_alfa.png"
        if not sin_color.exists() or not alfa.exists():
            continue
        im_.colorear(
            Image.open(sin_color).convert("RGB"), Image.open(alfa).convert("L"), i.color, tono, a
        ).save(carpeta / img.file, quality=a.lienzo.calidad_jpg)
    batch.color, batch.tone = i.color, tono
    return batch
