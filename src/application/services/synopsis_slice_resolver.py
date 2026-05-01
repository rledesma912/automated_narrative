"""SynopsisSliceResolver — segmenta sinopsis por beat según estrategia."""

import logging
import re

logger = logging.getLogger(__name__)

class SynopsisSliceResolver:
    """Divide la sinopsis en segmentos y los asigna a cada beat."""

    FALLBACK_SENTENCE_COUNT = 2

    def resolve(
        self,
        sinopsis: str,
        beat_number: int,
        total_beats: int,
        strategy: str,
    ) -> str:
        """Resuelve qué fragmento de sinopsis inyectar según la estrategia configurada."""
        if not sinopsis:
            return ""

        if strategy == "none":
            return ""
        if strategy == "full":
            return sinopsis

        return self.get_slice(sinopsis, beat_number, total_beats)

    def get_slice(self, sinopsis: str, beat_number: int, total_beats: int) -> str:
        """Divide la sinopsis en segmentos por párrafos y retorna el del beat actual.

        Si la sinopsis tiene menos párrafos que beats, retorna un fallback de oraciones
        iniciales para mantener el contexto global sin perder el hilo.
        """
        paragraphs = [p.strip() for p in sinopsis.split("\n\n") if p.strip()]

        if len(paragraphs) < total_beats:
            logger.debug(f"[SynopsisSliceResolver] Sinopsis con pocos párrafos ({len(paragraphs)}). Usando fallback de oraciones.")
            sentences = re.split(r"(?<=[.!?])\s+", sinopsis.strip())
            return " ".join(sentences[:self.FALLBACK_SENTENCE_COUNT]) if sentences else sinopsis

        segment_size = len(paragraphs) / total_beats
        start = int((beat_number - 1) * segment_size)
        end = int(beat_number * segment_size)

        # Asegurar al menos un párrafo si hay párrafos disponibles
        end = max(end, start + 1)

        # Limitar al máximo disponible
        end = min(end, len(paragraphs))

        return "\n\n".join(paragraphs[start:end])
