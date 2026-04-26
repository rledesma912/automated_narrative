"""SynopsisSliceResolver — segmenta sinopsis por beat según estrategia."""

import re


class SynopsisSliceResolver:
    """Divide la sinopsis en segmentos y los asigna a cada beat."""

    def resolve(
        self,
        sinopsis: str,
        beat_number: int,
        total_beats: int,
        strategy: str,
    ) -> str:
        """Resuelve qué fragmento de sinopsis inyectar según la estrategia configurada."""
        if strategy == "none":
            return ""
        if strategy == "full":
            return sinopsis
        return self.get_slice(sinopsis, beat_number, total_beats)

    def get_slice(self, sinopsis: str, beat_number: int, total_beats: int) -> str:
        """Divide la sinopsis en segmentos por párrafos y retorna el del beat actual.

        Si la sinopsis tiene menos párrafos que beats, retorna las primeras 2 oraciones
        como contexto general.
        """
        paragraphs = [p.strip() for p in sinopsis.split("\n\n") if p.strip()]

        if len(paragraphs) < total_beats:
            sentences = re.split(r"(?<=[.!?])\s+", sinopsis.strip())
            return " ".join(sentences[:2]) if sentences else sinopsis

        segment_size = len(paragraphs) / total_beats
        start = int((beat_number - 1) * segment_size)
        end = int(beat_number * segment_size)
        end = max(end, start + 1)
        return "\n\n".join(paragraphs[start:end])
