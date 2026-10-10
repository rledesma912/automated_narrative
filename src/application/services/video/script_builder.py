"""De la respuesta de la IA al paquete guardado (Spec-610 §3.2), con sus chequeos.

Nada de esto llama a la IA: revisa lo que devolvió y, si algo no cumple, devuelve la
lista de problemas (para el reintento). Si cumple, arma el `VideoScript`: énfasis a
posiciones, tipos al azar con la semilla de la variante, transiciones de la lista y el
lector propuesto según quién narra.
"""

import hashlib
import re
from uuid import UUID

from src.application.services.narrative_acts import NarrativeActs
from src.application.services.template_loader import TemplateLoader
from src.application.services.video import type_mix
from src.application.services.video.config import VideoConfig, estructura_del_relato
from src.application.services.video.schema import BloqueIA, PaqueteIA
from src.domain.video import Mark, PresenterLines, ReadingBlock, VideoScript, VisualMoment

# Un largo de la calabaza fuera del rango se acepta hasta este margen: el modelo cuenta
# palabras a ojo, y una intro de 85 palabras en vez de 80 no justifica rearmar todo.
MARGEN_LARGO = 0.25

_NEGATED = re.compile(r"\b(?:no|without)\s+\w+", re.I)


def narrative_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def words_of(text: str) -> list[str]:
    return text.split()


def _key(word: str) -> str:
    """Una palabra para comparar: minúsculas y sin signos alrededor («¿Qué?» → «qué»)."""
    return re.sub(r"^\W+|\W+$", "", word.lower())


def find_phrase(tokens: list[str], phrase: str, taken: set[int]) -> tuple[int, int] | None:
    """Primera aparición de `phrase` en `tokens` que no pisa posiciones ya marcadas."""
    wanted = [_key(w) for w in phrase.split() if _key(w)]
    if not wanted:
        return None
    keys = [_key(t) for t in tokens]
    for start in range(len(keys) - len(wanted) + 1):
        span = range(start, start + len(wanted))
        if keys[start : start + len(wanted)] == wanted and not taken.intersection(span):
            return start, start + len(wanted) - 1
    return None


class VideoScriptBuilder:
    def __init__(self, config: VideoConfig, templates: TemplateLoader | None = None) -> None:
        self.config = config
        self.templates = templates or TemplateLoader()

    # ── Chequeos ─────────────────────────────────────────────────────────────

    def check(self, paquete: PaqueteIA, narrative: NarrativeActs) -> list[str]:
        """Lo que no cumple (texto para la IA en el reintento); vacío si está todo bien."""
        f = self.templates.fragment
        problems: list[str] = []
        counts = {n: len(narrative.paragraphs(n)) for n in narrative.numbers()}
        for label, items in (
            ("video/problemas/bloques_cobertura", paquete.bloques),
            ("video/problemas/momentos_cobertura", paquete.momentos),
        ):
            problems += self._coverage(label, items, counts)
        for i, b in enumerate(paquete.bloques, start=1):
            if b.acto not in counts:
                continue
            tokens = self._block_tokens(b, narrative)
            taken: set[int] = set()
            for phrase in b.enfasis:
                found = find_phrase(tokens, phrase, taken)
                if found is None:
                    problems.append(
                        f("video/problemas/enfasis", bloque=i, acto=b.acto, texto=phrase)
                    )
                else:
                    taken.update(range(found[0], found[1] + 1))
        total = sum(counts.values())
        # Spec-650: el corto tiene menos momentos (por cuántos actos tiene el relato).
        rango = self.config.biblia.para(estructura_del_relato(len(counts))).momentos
        desde, hasta = min(rango.desde, total), min(rango.hasta, total)
        if not desde <= len(paquete.momentos) <= hasta:
            problems.append(
                f(
                    "video/problemas/momentos_cantidad",
                    cantidad=len(paquete.momentos),
                    desde=desde,
                    hasta=hasta,
                )
            )
        for i, m in enumerate(paquete.momentos, start=1):
            word = self._forbidden(f"{m.prompt_imagen} {m.prompt_movimiento}")
            if word:
                problems.append(f("video/problemas/prohibida", momento=i, palabra=word))
        problems += self._presenter_checks(paquete)
        return problems

    def _coverage(self, label: str, items, counts: dict[int, int]) -> list[str]:
        f = self.templates.fragment
        problems = []
        per_act: dict[int, list[int]] = {}
        for item in items:
            if item.acto not in counts:
                problems.append(f("video/problemas/acto_inexistente", acto=item.acto))
                continue
            per_act.setdefault(item.acto, []).extend(range(item.desde, item.hasta + 1))
        for act, total in counts.items():
            covered = per_act.get(act, [])
            details = []
            missing = [n for n in range(1, total + 1) if n not in covered]
            repeated = sorted({n for n in covered if covered.count(n) > 1})
            beyond = sorted({n for n in covered if n > total})
            if missing:
                details.append(f("video/problemas/faltan", numeros=_numbers(missing)))
            if repeated:
                details.append(f("video/problemas/repetidos", numeros=_numbers(repeated)))
            for n in beyond:
                details.append(f("video/problemas/no_existe", numero=n, total=total))
            if details:
                problems.append(f(label, acto=act, detalle="; ".join(details)))
        return problems

    def _forbidden(self, prompt: str) -> str | None:
        """Una palabra prohibida del prompt, sin contar las negadas («no people»)."""
        text = _NEGATED.sub(" ", prompt)
        for word in self.config.biblia.palabras_prohibidas:
            if re.search(rf"\b{re.escape(word)}\b", text, re.I):
                return word
        return None

    def _presenter_checks(self, paquete: PaqueteIA) -> list[str]:
        f = self.templates.fragment
        p = self.config.presentador
        problems = []
        cierre = p.outro.cierra_con.rstrip(".!… ")
        if not paquete.outro.strip().rstrip(".!… ").endswith(cierre):
            problems.append(f("video/problemas/outro_cierre", cierre=p.outro.cierra_con))
        for part, text, rango in (
            ("largo_intro", paquete.intro, p.intro.palabras),
            ("largo_outro", paquete.outro, p.outro.palabras),
        ):
            n = len(text.split())
            if not rango.desde * (1 - MARGEN_LARGO) <= n <= rango.hasta * (1 + MARGEN_LARGO):
                problems.append(
                    f(f"video/problemas/{part}", palabras=n, desde=rango.desde, hasta=rango.hasta)
                )
        return problems

    @staticmethod
    def _block_tokens(block, narrative: NarrativeActs) -> list[str]:
        paragraphs = narrative.paragraphs(block.acto)[block.desde - 1 : block.hasta]
        return [w for p in paragraphs for w in words_of(p)]

    # ── Armado ───────────────────────────────────────────────────────────────

    def build(
        self, paquete: PaqueteIA, narrative: NarrativeActs, narrative_id: UUID, content: str
    ) -> VideoScript:
        """El paquete listo para guardar. Se llama solo si `check()` no dio problemas."""
        cfg = self.config
        bloques = sorted(paquete.bloques, key=lambda b: (b.acto, b.desde))
        momentos = sorted(paquete.momentos, key=lambda m: (m.acto, m.desde))
        seed = type_mix.seed_for(narrative_id)
        biblia = cfg.biblia.para(estructura_del_relato(len(narrative.numbers())))  # Spec-650
        tipos = type_mix.assign([m.fuerte for m in momentos], biblia, seed)
        transiciones = {t.lower(): t for t in cfg.biblia.transiciones}
        return VideoScript(
            narrative_id=narrative_id,
            narra=paquete.narra,
            lector=cfg.lectores.propuesto(paquete.narra),
            bloques=[self._block(b, narrative) for b in bloques],
            momentos=[
                VisualMoment(
                    acto=m.acto,
                    desde=m.desde,
                    hasta=m.hasta,
                    fuerte=m.fuerte,
                    tipo=tipo,
                    que_se_ve=m.que_se_ve.strip(),
                    lugar=m.lugar.strip(),
                    prompt_imagen=m.prompt_imagen.strip(),
                    prompt_movimiento=m.prompt_movimiento.strip(),
                    transicion=transiciones.get(m.transicion.strip().lower(), "Corte"),
                    sonido=m.sonido.strip(),
                )
                for m, tipo in zip(momentos, tipos, strict=True)
            ],
            calabaza=PresenterLines(intro=paquete.intro.strip(), outro=paquete.outro.strip()),
            parrafos_por_acto={n: len(narrative.paragraphs(n)) for n in narrative.numbers()},
            narrative_hash=narrative_hash(content),
            seed=seed,
        )

    def _block(self, b: BloqueIA, narrative: NarrativeActs) -> ReadingBlock:
        tokens = self._block_tokens(b, narrative)
        taken: set[int] = set()
        marks = []
        for phrase in b.enfasis:
            found = find_phrase(tokens, phrase, taken)
            if found is None:
                continue
            taken.update(range(found[0], found[1] + 1))
            marks.append(
                Mark(
                    desde_palabra=found[0],
                    hasta_palabra=found[1],
                    texto=" ".join(tokens[found[0] : found[1] + 1]),
                )
            )
        return ReadingBlock(
            acto=b.acto,
            desde=b.desde,
            hasta=b.hasta,
            indicacion=b.indicacion.strip(),
            pausa=b.pausa,
            marcas=sorted(marks, key=lambda m: m.desde_palabra),
        )


def _numbers(numbers: list[int]) -> str:
    return ", ".join(str(n) for n in numbers)
