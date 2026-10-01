"""Los PDF del paquete para el video (Spec-610 §3.7.3, §3.7.4; D24: WeasyPrint).

El diseño vive en `config/video/pdf/` (plantillas Jinja2 + CSS para imprimir en blanco y
negro): acá solo se arman los datos. El texto del relato se lee del relato actual; las
marcas se reubican como en la pantalla (`state.relocate`).
"""

from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from src.application.services import narrative_acts
from src.application.services.video import files, timing
from src.application.services.video import state as video_state
from src.application.services.video.config import VideoConfig
from src.domain.video import VideoScript

_ROOT = Path(__file__).resolve().parents[4]
TEMPLATES_DIR = _ROOT / "config" / "video" / "pdf"
FONTS_DIR = _ROOT / "assets" / "fonts"
WORDS_AT_EDGES = 7  # «Entra cuando dice…» / «Hasta…» en el mapa


@dataclass
class Timeline:
    """Segundo en que empieza cada párrafo del relato (después de la intro)."""

    intro: int
    starts: dict[tuple[int, int], int]
    end: int
    outro: int

    @property
    def total(self) -> int:
        return self.end + self.outro


def timeline(
    script: VideoScript, acts: narrative_acts.NarrativeActs, config: VideoConfig
) -> Timeline:
    ppm = config.lectura.palabras_por_minuto
    seg = lambda text: timing.segundos(timing.palabras(text), ppm)  # noqa: E731
    t = intro = seg(script.calabaza.intro)
    starts = {}
    for n in acts.numbers():
        for i, p in enumerate(acts.paragraphs(n), start=1):
            starts[(n, i)] = t
            t += seg(p)
    outro = seg(f"{script.calabaza.outro} {config.presentador.cierre_fijo}")
    return Timeline(intro=intro, starts=starts, end=t, outro=outro)


def _marked_paragraphs(acts, block) -> list[Markup]:
    """Los párrafos del bloque, con lo remarcado en <strong> (palabras o frases)."""
    tokens = video_state.block_tokens(acts, block.acto, block.desde, block.hasta)
    kept, _ = video_state.relocate(tokens, block.marcas)
    marked = {k for m in kept for k in range(m.desde_palabra, m.hasta_palabra + 1)}
    out, k = [], 0
    for paragraph in acts.paragraphs(block.acto)[block.desde - 1 : block.hasta]:
        html, open_ = [], False
        for j, word in enumerate(paragraph.split()):
            is_marked = k in marked
            if is_marked and not open_:
                html.append((" " if j else "") + "<strong>")
                open_ = True
            elif not is_marked and open_:
                html.append("</strong> ")
                open_ = False
            elif j:
                html.append(" ")
            html.append(str(escape(word)))
            k += 1
        if open_:
            html.append("</strong>")
        out.append(Markup("".join(html)))
    return out


def guion_context(script: VideoScript, content: str, title: str, config: VideoConfig) -> dict:
    acts = narrative_acts.split(content)
    line = timeline(script, acts, config)
    ppm = config.lectura.palabras_por_minuto
    numbered = list(enumerate(script.bloques, start=1))
    actos = []
    for n in acts.numbers():
        bloques = [
            {
                "numero": i,
                "inicio": timing.reloj(line.starts.get((b.acto, b.desde), 0)),
                "indicacion": b.indicacion,
                "parrafos": _marked_paragraphs(acts, b),
                "pausa": b.pausa,
            }
            for i, b in numbered
            if b.acto == n
        ]
        actos.append(
            {
                "numero": n,
                "desde": timing.reloj(line.starts.get((n, 1), 0)),
                "bloques": bloques,
            }
        )
    words = sum(timing.palabras(acts.acts[n]) for n in acts.numbers())
    return {
        "titulo": title,
        "lector": script.lector or "",
        "minutos": round(line.total / 60),
        "duracion_relato": timing.largo(timing.segundos(words, ppm)),
        "bloques_total": len(script.bloques),
        "actos": actos,
        "fuentes": FONTS_DIR.as_uri(),
    }


def mapa_context(script: VideoScript, content: str, title: str, config: VideoConfig) -> dict:
    acts = narrative_acts.split(content)
    line = timeline(script, acts, config)
    tipos = config.biblia.tipos
    estilo = config.biblia.estilo.strip()
    total = max(line.total, 1)
    pct = lambda s: round(s / total * 100, 3)  # noqa: E731
    fichas = []
    for i, m in enumerate(script.momentos, start=1):
        start = line.starts.get((m.acto, m.desde), 0)
        paragraphs = acts.paragraphs(m.acto)[m.desde - 1 : m.hasta] if m.acto in acts.acts else []
        words = " ".join(paragraphs).split()
        dur = timing.segundos(len(words), config.lectura.palabras_por_minuto)
        fichas.append(
            {
                "numero": i,
                "ancla": f"m{i}",
                "tipo": m.tipo,
                "tipo_nombre": tipos[m.tipo].nombre,
                "se_genera_con": tipos[m.tipo].se_genera_con,
                "que_se_ve": m.que_se_ve,
                "acto": m.acto,
                "desde": timing.reloj(start),
                "hasta": timing.reloj(start + dur),
                "segundos": dur,
                "pct": pct(dur),
                "entra": " ".join(words[:WORDS_AT_EDGES]),
                "sale": " ".join(words[-WORDS_AT_EDGES:]),
                "prompt_imagen": f"{estilo} {m.prompt_imagen}".strip(),
                "prompt_movimiento": m.prompt_movimiento if m.tipo != "imagen" else "",
                "transicion": m.transicion,
                "sonido": m.sonido,
                "archivos": files.file_names(i, m.lugar, m.tipo),
            }
        )
    base = f"calabaza-{files.slug(title, limit=40)}"
    return {
        "titulo": title,
        "duracion": timing.reloj(line.total),
        "momentos_total": len(fichas),
        "cuenta": {
            t: sum(1 for f in fichas if f["tipo"] == t) for t in ("imagen", "animacion", "video")
        },
        "intro": {
            "pct": pct(line.intro),
            "desde": "0:00",
            "hasta": timing.reloj(line.intro),
            "segundos": line.intro,
            "archivo": f"{base}-intro.mp3",
        },
        "outro": {
            "pct": pct(line.outro),
            "desde": timing.reloj(line.end),
            "hasta": timing.reloj(line.total),
            "segundos": line.outro,
            "archivo": f"{base}-outro.mp3",
        },
        "fichas": fichas,
        "marcas_minutos": [
            {"pct": pct(s), "texto": f"{s // 60}′"} for s in range(0, line.total, 120)
        ],
        "fuentes": FONTS_DIR.as_uri(),
    }


_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_html(template: str, context: dict) -> str:
    return _env.get_template(template).render(**context)


def render_pdf(template: str, context: dict) -> bytes:
    from weasyprint import HTML  # import tardío: la carga de pango es lenta

    return HTML(string=render_html(template, context), base_url=str(TEMPLATES_DIR)).write_pdf()
