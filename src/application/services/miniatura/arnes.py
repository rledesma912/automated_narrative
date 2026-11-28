"""El arnés de las miniaturas (Spec-790 D15, §10.7): Python ordena, ComfyUI hace una cosa por vez.

  textos      la IA separa lo que escribió Yael: personaje solo, lugar vacío y relación (T3.3)
  personaje   boceto → `boceto_a_imagen` (prompts/personaje.md) → `recortar` → PNG con alfa
  escenario   boceto → `boceto_a_imagen` (prompts/escenario.md) → curva en Python →
              `foto_controlnet` con el boceto de guía (prompts/fotografiar_escenario.md, T6.6)
              → `recortar` (lo importante)
  fotos       Spec-820 S2: la IA escribe el prompt de la foto de cada plantilla mirando los
              bocetos y las referencias de luz (`referencias/`); sin IA, el fijo
  4 opciones  Spec-820, por plantilla: ubicar → espejar si tapa lo importante → la composición
              con la luz de Yael (niebla clara, figura en silueta, halo, ojos; el tronco delante
              si está escondida) → guía de profundidad → `foto_controlnet` (una sola foto) →
              niveles → `recortar` la figura → despegar y mate → color → JPG

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
from src.application.services.miniatura.arte import CONFIG, Arte, prompt, texto
from src.application.services.miniatura.arte import arte as cargar_arte
from src.config import settings
from src.domain.interfaces import LLMProvider
from src.domain.jobs import JobStage
from src.domain.thumbnail import Batch, ImageTexts, Part, Thumbnail, ThumbnailImage
from src.infrastructure.adapters.comfy.client import ComfyError, ComfyPort
from src.messages import message

REFERENCIAS = CONFIG / "referencias"  # Spec-820 S2: miniaturas de Yael, solo para la luz
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
        # T6.5: la IA mira los bocetos, así que cambiar uno vuelve a leer.
        bocetos = [self.carpeta / i.character_sketch, self.carpeta / i.scene_sketch]
        h = _hash(
            i.figure_description,
            i.place_description,
            *(b.read_bytes() for b in bocetos),
            texto("ia_sistema"),
            "textos-v2",
        )
        if thumb.texts and thumb.texts.input_hash == h:
            return thumb.texts
        if self.llm is None:
            return ImageTexts(
                personaje=i.figure_description, escenario=i.place_description, input_hash=h
            )
        thumb.texts = await textos_.separar(self.llm, i, h, bocetos)
        return thumb.texts

    # ── los prompts de la foto (Spec-820 S2) ─────────────────────────────────────
    async def fotos(self, thumb: Thumbnail, txt: ImageTexts) -> dict[str, str]:
        """Uno por plantilla; se reusan mientras no cambien los textos, la guía ni las
        referencias. Sin IA, el fijo."""
        i = thumb.input
        bocetos = [self.carpeta / i.character_sketch, self.carpeta / i.scene_sketch]
        refs = textos_.referencias(REFERENCIAS)
        h = _hash(
            txt.input_hash,
            texto("ia_foto_sistema"),
            texto("ia_foto_pedido"),
            texto("una_foto"),
            *self.arte.plantillas,
            *(r.read_bytes() for r in refs),
            "fotos-v1",
        )
        if txt.fotos and txt.fotos_hash == h:
            return txt.fotos
        if self.llm is None:
            escondida = txt.a_medio_ver == "mucho"
            txt.fotos = {
                k: textos_.foto_fija(txt, escondida and k in self.arte.fundido.detras_en)
                for k in self.arte.plantillas
            }
        else:
            txt.fotos = await textos_.prompts_de_foto(self.llm, i, txt, bocetos, refs, self.arte)
        txt.fotos_hash = h
        return txt.fotos

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
            f"escenario-v2-{self.arte.escenario.cambio_foto}-{self.arte.escenario.guia}",
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
        guia = piezas / "escenario_guia.png"
        im_.scribble(Image.open(boceto)).save(guia)
        foto = await self.comfy.correr(
            "foto_controlnet",
            {
                "prompt": prompt("fotografiar_escenario", desc),
                "semilla": semilla,
                "cambio": self.arte.escenario.cambio_foto,
                "fuerza": self.arte.escenario.guia,
            },
            {"imagen": oscuro, "guia": guia},
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
        fotos = await self.fotos(thumb, txt)
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
        # T6.7 → Spec-820: escondida (detrás de un árbol, asomándose): en `detras_en` Python pone
        # un tronco delante y la guía lo marca como lo más cercano.
        escondida = txt.a_medio_ver == "mucho"
        for k, (clave, p) in enumerate(self.arte.plantillas.items(), start=1):
            detras = escondida and clave in self.arte.fundido.detras_en
            yield Etapa(JobStage.COMPONIENDO, k, total)
            f, pos = im_.ubicar(im_.figura_recortada(figura, p.recorte), p, apoyo, self.arte)
            alfa = im_.alfa_en_cuadro(f, pos, self.arte)
            espejo = im_.espejo_conviene(alfa, importante)
            fondo = im_.lienzo(escenario, self.arte, espejo)
            comp = im_.componer_con_luz(fondo, f, pos, alfa, self.arte)
            tronco = im_.mascara_tronco(alfa, self.arte) if detras else None
            if tronco is not None:
                comp = im_.pegar_tronco(comp, tronco, semilla + k, self.arte)
            comp_png, guia_png = (
                carpeta_tanda / f"{clave}_comp.png",
                carpeta_tanda / f"{clave}_guia.png",
            )
            comp.save(comp_png)
            im_.profundidad(comp, alfa, self.arte, tronco).save(guia_png)
            cambio, fuerza = self.arte.foto(clave)
            # Tanda 18: a veces la foto inventa una cabeza de más (dos pares de ojos). Se nota
            # sin IA y se rehace una vez con otra semilla; si insiste, queda la segunda.
            for intento in range(2):
                foto = await self.comfy.correr(
                    "foto_controlnet",
                    {
                        "prompt": fotos[clave],
                        "semilla": semilla + k + 1000 * intento,
                        "cambio": cambio,
                        "fuerza": fuerza,
                    },
                    {"imagen": comp_png, "guia": guia_png},
                    carpeta_tanda / f"{clave}_foto.png",
                )
                if intento or im_.contar_ojos(Image.open(foto)) < 4:  # dos pares = otra cabeza
                    break
            control = im_.controlar_luz(Image.open(foto).convert("RGB"), self.arte)
            control_png = carpeta_tanda / f"{clave}_control.png"
            control.save(control_png)
            # la figura donde quedó en la foto (la foto la mueve un poco al reinterpretar)
            mascara = await self.comfy.correr(
                "recortar", {}, {"imagen": control_png}, carpeta_tanda / f"{clave}_figura.png"
            )
            figura_foto = Image.open(mascara).convert("L").resize(control.size)
            final = im_.mate(im_.despegar(control, figura_foto, self.arte), figura_foto, self.arte)
            if p.modo == "respeta":  # al reinterpretar la figura se mueve (tanda 17)
                final = im_.devolver_ojos(final, comp, figura_foto, self.arte)
            final.save(carpeta_tanda / f"{clave}_sin_color.png")
            figura_foto.save(carpeta_tanda / f"{clave}_alfa.png")
            jpg = carpeta_tanda / f"{clave}.jpg"
            im_.colorear(final, figura_foto, i.color, tono, self.arte).save(
                jpg, quality=self.arte.lienzo.calidad_jpg
            )
            batch.luz[clave] = im_.medir_luz(Image.open(jpg))
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
