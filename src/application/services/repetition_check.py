"""Control de repetición de un relato (Spec-530 §8.3), sin LLM.

Por acto: las frases (4 palabras) que repite de un acto anterior y los clichés
prohibidos, buscados por lema (raíz de cada palabra, con hasta 2 palabras
intercaladas) para que «me había helado la sangre» cuente como «me heló la sangre».
"""

import re
import unicodedata
from dataclasses import dataclass, field

from src.application.services.beat_spec_repository import BeatSpecRepository
from src.application.services.voice_cliches import load_cliches

_MIN_PREFIX = 3  # letras en común para considerar dos palabras la misma raíz
_MAX_GAP = 2  # palabras intercaladas admitidas en un cliché
_MAX_PHRASES = 5


@dataclass
class ActRepetition:
    number: int
    # (frase, acto donde ya estaba): el texto lo arma quien la muestra (Spec-620)
    repeated: list[tuple[str, int]] = field(default_factory=list)
    cliches: list[str] = field(default_factory=list)
    invented_names: list[str] = field(
        default_factory=list
    )  # nombres propios que la historia no tiene
    # Spec-590 F: oraciones cortadas (hasta 3 ejemplos, el total y el % de la narración)
    # y fragmentos de diálogo directo.
    cut_sentences: list[str] = field(default_factory=list)
    cut_count: int = 0
    cut_pct: int = 0
    dialogue: int = 0
    # Spec-640: comparaciones de escritor (hasta 3 ejemplos y el total).
    comparisons: list[str] = field(default_factory=list)
    comparison_count: int = 0

    @property
    def too_cut(self) -> bool:
        """Un fragmento suelto está bien; se avisa cuando pasa a ser el estilo del acto."""
        return self.cut_pct >= CUT_PCT_WARNING

    @property
    def too_literary(self) -> bool:
        """Spec-640 D2: una comparación por acto está bien; desde la segunda, se avisa."""
        return self.comparison_count > COMPARISONS_PER_ACT

    def has_findings(self) -> bool:
        return bool(
            self.repeated
            or self.cliches
            or self.invented_names
            or self.too_cut
            or self.dialogue
            or self.too_literary
        )


def _tokens(text: str) -> tuple[list[str], list[str]]:
    """Palabras originales (para mostrar) y normalizadas sin tildes (para comparar)."""
    original = re.findall(r"\w+", text.lower())
    norm = []
    for w in original:
        t = unicodedata.normalize("NFKD", w)
        norm.append("".join(ch for ch in t if not unicodedata.combining(ch)))
    return original, norm


def _content(gram: tuple[str, ...]) -> bool:
    """Al menos dos palabras con contenido: «de la que se» no cuenta como repetición."""
    return sum(len(w) > 3 for w in gram) >= 2


# Nombres que se escriben con mayúscula sin ser personajes ni lugares inventados.
_NOT_INVENTED = {"dios", "señor", "padrenuestro", "padre", "nuestro", "virgen", "ave", "maría"}

_NAME = re.compile(r"(?<=[a-záéíóúñ,;:] )([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?: [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)")


def invented_names(text: str, known: str) -> list[str]:
    """Nombres propios en medio de una frase que no aparecen en lo que cargó el autor.

    `known` es todo el texto de autoría (elenco, escaleta, dirección, amenaza). Una
    palabra que también aparece en minúscula en el relato no cuenta como nombre.
    """
    known_words = {w.lower() for w in re.findall(r"\w+", known)} | _NOT_INVENTED
    lowered = set(re.findall(r"\b[a-záéíóúñ]+\b", text))
    found: list[str] = []
    for name in _NAME.findall(text):
        words = name.lower().split()
        if all(w in known_words or w in lowered for w in words) or name in found:
            continue
        found.append(name)
    return found


# ── Oraciones cortadas y diálogo (Spec-590 F) ───────────────────────────────
# Heurística sin dependencias: una oración tiene verbo conjugado si alguna palabra
# termina en una desinencia finita o es un verbo irregular común. Gerundios e
# infinitivos no cuentan. Es un aviso: se aceptan falsos positivos.

_SHORT = 5  # menos palabras que esto = oración cortada, aunque tenga verbo
_MAX_EXAMPLES = 3
CUT_PCT_WARNING = 25  # % de oraciones cortadas desde el que se avisa

_IRREGULAR = set(
    "es son era eran fue fueron fui hay había habían hubo he ha han has "
    "está están estaba estaban estoy estuve estuvo vi vio veo ve veía dijo dije digo dice "
    "pude pudo puedo puede podía quise quiso quiero quería tuve tuvo tengo tiene tenía "
    "hice hizo hago hace iba iban voy va van sé sabía sabe supe supo soy sos "
    "vino vine dio di doy da oí oyó oía siento siente sentí sintió pienso piensa "
    "debo debe debía cayó caí traje trajo seguí siguió pidió pedí murió durmió "
    "fuera fueran".split()
)
# Terminan como un verbo y no lo son.
_NOT_VERB = set(
    "aquí allí así ahí sí mí ti qué fe café bebé mamá papá allá acá sofá más jamás atrás "
    "día días tía tías vía policía compañía energía alegría".split()
)
_FINITE = re.compile(
    r"(?:[éóí]|aste|iste|aron|ieron|yeron|amos|emos|imos|aba|abas|aban|ábamos"
    r"|ía|ías|ían|íamos|á|án|ás|iera|ieras|ieran|iese|iesen|aran)$"
)
# Antes de un presente («me duele», «no sabe»): pronombres átonos, sujeto y «no».
_BEFORE_PRESENT = set("me te se le les nos yo no él ella ellos ellas vos".split())
_PRESENT = re.compile(r"(?:[oae]|as|es|an|en)$")

_SENTENCE_END = re.compile(r"(?<=[.!?…])[»”\"]?\s+|\n+")
_DIALOGUE_LINE = re.compile(r"^\s*[—–-]", re.M)
_QUOTE = re.compile(r"“[^”]+”|\"[^\"]+\"|«[^»]+»")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text) if re.search(r"\w", s)]


def has_finite_verb(sentence: str) -> bool:
    words = re.findall(r"\w+", sentence.lower())
    for i, w in enumerate(words):
        if w in _NOT_VERB:
            continue
        if w in _IRREGULAR or _FINITE.search(w):
            return True
        if i and words[i - 1] in _BEFORE_PRESENT and _PRESENT.search(w):
            return True
    return False


def narration_sentences(text: str) -> list[str]:
    """Las oraciones de la narración: sin líneas de diálogo ni frases entre comillas."""
    return split_sentences(_QUOTE.sub(" ", _DIALOGUE_LINE.sub("", text)))


def cut_sentences(text: str) -> list[str]:
    """Oraciones sin verbo conjugado o de menos de 5 palabras (sin contar el diálogo)."""
    return [
        s
        for s in narration_sentences(text)
        if len(re.findall(r"\w+", s)) < _SHORT or not has_finite_verb(s)
    ]


def dialogue_lines(text: str) -> list[str]:
    """Diálogo directo: líneas con raya o guion, y frases entre comillas (las «» con
    menos de 3 palabras suelen ser una palabra citada, no alguien hablando)."""
    lines = [ln.strip() for ln in text.splitlines() if _DIALOGUE_LINE.match(ln)]
    quotes = [
        q for q in _QUOTE.findall(text) if not q.startswith("«") or len(re.findall(r"\w+", q)) >= 3
    ]
    return lines + quotes


# ── Spec-640: comparaciones («como si…», «como una cortina») ────────────────
# Lo literario que se puede contar sin IA. «como a las cuatro», «como siempre» o
# «como yo» no son comparaciones de escritor y no cuentan.

COMPARISONS_PER_ACT = 1  # Spec-640 D2: las que admite un acto sin aviso
_COMPARISON = re.compile(r"\bcomo (?:si|una?)\b(?:\s+[\wáéíóúñü]+){1,4}", re.I)


def comparisons(text: str) -> list[str]:
    """Las comparaciones de la narración, desde «como» hasta 5 palabras."""
    narration = "\n".join(ln for ln in text.splitlines() if not _DIALOGUE_LINE.match(ln))
    return [m.group(0) for s in narration_sentences(narration) for m in _COMPARISON.finditer(s)]


def check(
    acts: list[str], cliches: list[str] | None = None, known: str | None = None
) -> list[ActRepetition]:
    expressions = cliches if cliches is not None else load_cliches()
    tokens = [_tokens(a) for a in acts]
    grams = [
        {tuple(ws[i : i + 4]) for i in range(len(ws) - 3) if _content(tuple(ws[i : i + 4]))}
        for _, ws in tokens
    ]
    result = []
    for n, (orig, ws) in enumerate(tokens):
        rep = ActRepetition(number=n + 1)
        i = 0
        while i < len(ws) - 3:
            g = tuple(ws[i : i + 4])
            first = next((k for k in range(n) if g in grams[k]), None) if _content(g) else None
            if first is None:
                i += 1
                continue
            # Se extiende mientras siga repitiendo el mismo acto: una frase, no pedazos.
            end = i
            while end + 1 < len(ws) - 3 and tuple(ws[end + 1 : end + 5]) in grams[first]:
                end += 1
            phrase = (" ".join(orig[i : end + 4]), first + 1)
            if phrase not in rep.repeated and len(rep.repeated) < _MAX_PHRASES:
                rep.repeated.append(phrase)
            i = end + 4
        found: dict[tuple[str, ...], str] = {}
        for c in expressions:
            key = tuple(w for w in _tokens(c)[1] if len(w) > 2)
            if key not in found and _has_cliche(ws, c):
                found[key] = c  # «se me heló la sangre» y «me heló la sangre» son uno solo
        rep.cliches = list(found.values())
        if known is not None:
            rep.invented_names = invented_names(acts[n], known)
        cut, total = cut_sentences(acts[n]), len(narration_sentences(acts[n]))
        rep.cut_sentences = cut[:_MAX_EXAMPLES]
        rep.cut_count = len(cut)
        rep.cut_pct = round(100 * len(cut) / total) if total else 0
        rep.dialogue = len(dialogue_lines(acts[n]))
        found_comparisons = comparisons(acts[n])
        rep.comparisons = found_comparisons[:_MAX_EXAMPLES]
        rep.comparison_count = len(found_comparisons)
        result.append(rep)
    return result


def _same_root(a: str, b: str) -> bool:
    common = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        common += 1
    # Palabras de 1 o 2 letras («si», «se») nunca cuentan como la raíz de otra.
    return common >= _MIN_PREFIX and common >= min(len(a), len(b)) - 2


def _has_cliche(words: list[str], expression: str) -> bool:
    target = [w for w in _tokens(expression)[1] if len(w) > 2]
    if not target:
        return False
    for start, w in enumerate(words):
        if not _same_root(w, target[0]):
            continue
        pos, ok = start, True
        for t in target[1:]:
            window = words[pos + 1 : pos + 2 + _MAX_GAP]
            hit = next((k for k, x in enumerate(window) if _same_root(x, t)), None)
            if hit is None:
                ok = False
                break
            pos = pos + 1 + hit
        if ok:
            return True
    return False


# ── Spec-560 A2/A6: lo detectado vuelve a la Voz cuando el autor pide rehacer ──


def known_text(story) -> str:
    """Todo lo que cargó el autor: de acá salen los nombres que la Voz puede usar."""
    parts = [story.title, story.sinopsis, story.protagonista]
    parts += [p.get("name", "") + " " + p.get("relation", "") for p in story.personajes_full]
    parts += [s.name + " " + s.description for s in story.scenarios]
    parts += [e.name + " " + e.description + " " + e.manifestations for e in story.entities]
    for act in story.outline:
        parts += [act.goal, act.scenario, *act.events, *act.on_stage]
    if story.direction:
        parts += [story.direction.premise, story.direction.ending]
    parts += [w.answer for w in story.workshop]
    return " ".join(p for p in parts if p)


def last_version_findings(story) -> dict[int, ActRepetition]:
    """Lo que el control marca en la última prosa de cada acto (macro_beat)."""
    beats = sorted((b for b in story.beats if b.generated_act), key=lambda b: b.number)
    if not beats:
        return {}
    # Spec-650: la prosa guardada es de otra estructura (no debería pasar: cambiar el largo
    # la borra) → lo que marcó no corresponde a estos actos.
    if beats[-1].number > BeatSpecRepository().estructura(story.structure).num_actos:
        return {}
    reps = check([b.generated_act for b in beats], known=known_text(story))
    return {b.number: r for b, r in zip(beats, reps, strict=True) if r.has_findings()}
