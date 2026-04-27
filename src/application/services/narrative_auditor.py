"""NarrativeAuditor — evalúa si una respuesta del LLM aplica conceptos o los explica (Spec-170)."""

import logging
import re

from src.domain.interfaces import AuditResult

logger = logging.getLogger(__name__)

# Frases que indican que el modelo está explicando en lugar de aplicar
_BOILERPLATE_PATTERNS = [
    r"hamartia\s+es\b",
    r"hybris\s+es\b",
    r"anagnórisis\s+es\b",
    r"peripeteia\s+es\b",
    r"se\s+refiere\s+a",
    r"es\s+el\s+concepto",
    r"según\s+aristóteles",
    r"la\s+pirámide\s+de\s+freytag",
    r"este\s+pilar\s+(representa|indica|captura)",
    r"en\s+términos\s+narrativos",
    r"en\s+la\s+teoría\s+literaria",
    r"este\s+estadio\s+(de|del)",
]

_BOILERPLATE_RE = re.compile(
    "|".join(_BOILERPLATE_PATTERNS),
    re.IGNORECASE,
)

_SENSORY_WORDS = frozenset(
    {
        "ver",
        "vio",
        "vieron",
        "mirar",
        "miró",
        "miraban",
        "percibir",
        "percibió",
        "oír",
        "oyó",
        "escuchar",
        "escuchó",
        "escuchaban",
        "tocar",
        "tocó",
        "palpar",
        "palpó",
        "oler",
        "olió",
        "olfatear",
        "sentir",
        "sintió",
        "manos",
        "piel",
        "ojos",
        "labios",
        "dedos",
        "pies",
        "cuerpo",
        "frío",
        "calor",
        "oscuridad",
        "silencio",
        "ruido",
        "olor",
        "sangre",
        "barro",
        "polvo",
        "vapor",
        "sombra",
        "luz",
        "llanto",
        "crujido",
        "eco",
        "temblor",
        "latido",
    }
)


def _word_tokens(text: str) -> list[str]:
    return re.findall(r"[a-záéíóúüñ]+", text.lower())


def _section_bodies(response: str) -> list[str]:
    """Extrae el cuerpo de cada sección ## del response."""
    parts = re.split(r"^##\s*\w+", response, flags=re.MULTILINE)
    return [p.strip() for p in parts if p.strip()]


class NarrativeAuditor:
    """Auditor de alfabetismo narrativo con tres heurísticas (Spec-170).

    Heurísticas:
    - Boilerplate: el modelo explica conceptos en lugar de aplicarlos.
    - Sensoriality: escasa densidad de imágenes concretas / sensoriales.
    - Entropy: el texto es un calco literal de la sinopsis.
    """

    SENSORIALITY_MIN_DENSITY = 0.04  # al menos 4% de palabras sensoriales en el cuerpo
    ENTROPY_MAX_OVERLAP = 0.80  # más del 80% de solapamiento con la sinopsis = copia literal

    def validate(self, response: str, synopsis: str = "") -> AuditResult:
        if not response.strip():
            return AuditResult(passed=False, reason="respuesta vacía", score=0.0)

        penalties: list[str] = []
        score = 1.0

        # — Heurística 1: Boilerplate — falla sola (penalización total)
        if self._is_boilerplate(response):
            penalties.append("boilerplate: modelo define en lugar de aplicar")
            score -= 1.0

        # — Heurística 2: Sensoriality —
        if not self._has_sensoriality(response):
            penalties.append("sensoriality: densidad de imágenes concretas insuficiente")
            score -= 0.2

        # — Heurística 3: Entropy —
        if synopsis and self._is_synopsis_copy(response, synopsis):
            penalties.append("entropy: texto es calco literal de la sinopsis")
            score -= 0.2

        passed = score > 0.0
        reason = "; ".join(penalties) if penalties else "OK"

        if not passed:
            logger.debug("[AUDITOR] Fallo — %s (score=%.2f)", reason, score)
        else:
            logger.debug("[AUDITOR] OK (score=%.2f)", score)

        return AuditResult(passed=passed, reason=reason, score=max(0.0, score))

    # ── heurísticas privadas ─────────────────────────────────────────────────

    def _is_boilerplate(self, response: str) -> bool:
        return bool(_BOILERPLATE_RE.search(response))

    def _has_sensoriality(self, response: str) -> bool:
        bodies = _section_bodies(response)
        if not bodies:
            words = _word_tokens(response)
            return self._sensory_density(words) >= self.SENSORIALITY_MIN_DENSITY

        densities = []
        for body in bodies:
            words = _word_tokens(body)
            if words:
                densities.append(self._sensory_density(words))

        if not densities:
            return True  # sin secciones reconocibles → no penalizar
        return (sum(densities) / len(densities)) >= self.SENSORIALITY_MIN_DENSITY

    def _sensory_density(self, words: list[str]) -> float:
        if not words:
            return 0.0
        hits = sum(1 for w in words if w in _SENSORY_WORDS)
        return hits / len(words)

    def _is_synopsis_copy(self, response: str, synopsis: str) -> bool:
        resp_words = set(_word_tokens(response))
        syn_words = set(_word_tokens(synopsis))
        if len(resp_words) < 10:
            return False
        overlap = len(resp_words & syn_words) / len(resp_words)
        return overlap > self.ENTROPY_MAX_OVERLAP
