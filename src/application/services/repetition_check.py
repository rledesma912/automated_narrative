"""Control de repetición de un relato (Spec-530 §8.3), sin LLM.

Por acto: las frases (4 palabras) que repite de un acto anterior y los clichés
prohibidos, buscados por lema (raíz de cada palabra, con hasta 2 palabras
intercaladas) para que «me había helado la sangre» cuente como «me heló la sangre».
"""

import re
import unicodedata
from dataclasses import dataclass, field

from src.application.services.voice_cliches import load_cliches

_MIN_PREFIX = 3  # letras en común para considerar dos palabras la misma raíz
_MAX_GAP = 2  # palabras intercaladas admitidas en un cliché
_MAX_PHRASES = 5


@dataclass
class ActRepetition:
    number: int
    repeated: list[str] = field(default_factory=list)  # «frase» (del acto N)
    cliches: list[str] = field(default_factory=list)
    invented_names: list[str] = field(
        default_factory=list
    )  # nombres propios que la historia no tiene


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
            phrase = f"«{' '.join(orig[i : end + 4])}» (del acto {first + 1})"
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
