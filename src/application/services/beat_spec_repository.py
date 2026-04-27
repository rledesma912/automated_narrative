"""BeatSpecRepository — fuente de verdad del YAML de beats en memoria."""

import logging
from pathlib import Path

import yaml

from src.config import settings

logger = logging.getLogger(__name__)


class BeatSpecRepository:
    """Carga y expone el spec de macro-beats desde el YAML de definición."""

    def __init__(self, yaml_path: Path | None = None) -> None:
        self._path = yaml_path or Path(settings.beats_definition_file)
        self._beats: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if not self._path.exists():
            logger.warning(
                f"[BeatSpecRepository] beats_definition_file no encontrado: {self._path}. "
                "Usando 5 beats vacíos."
            )
            return [{"id": i, "name": f"beat_{i}"} for i in range(1, 6)]
        with self._path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("beats_spec", {}).get("macro_beats", [])

    @property
    def num_beats(self) -> int:
        return len(self._beats)

    def get_all(self) -> list[dict]:
        return list(self._beats)

    def get_by_id(self, beat_id: int) -> dict:
        return next((b for b in self._beats if b["id"] == beat_id), {})

    def get_word_limit(self, beat_id: int, default: str = "") -> str:
        """Retorna el word_limit configurado en el YAML para este beat."""
        beat = self.get_by_id(beat_id)
        return beat.get("word_limit", default)

    def format_compact(self) -> str:
        """Versión abreviada: solo id, name e intent. Usado por el mapper global."""
        lines = []
        for beat in self._beats:
            lines.append(f"Acto {beat['id']} ({beat['name']}): {beat.get('intent', '')}")
        return "\n".join(lines)

    def format_for_beat(self, beat_id: int, variant: str = "frontier") -> str:
        """Restricciones del YAML para un beat específico, usadas por VOZ."""
        beat = self.get_by_id(beat_id)
        if not beat:
            return ""

        if variant == "compact":
            parts = [f"Acto {beat['id']} — {beat['name']}: {beat.get('intent', '')}"]
            sc = beat.get("state_change", {})
            if sc:
                parts.append(f"Arco emocional: {sc.get('from', '')} → {sc.get('to', '')}")
            must = beat.get("must", [])
            if must:
                parts.append(f"Debe incluir: {' / '.join(must)}")
            must_not = beat.get("must_not", [])
            if must_not:
                parts.append(f"PROHIBIDO en este acto: {' / '.join(must_not)}")
            success = beat.get("success_signal", [])
            if success:
                parts.append(f"Objetivo del fragmento: {success[0]}")
            return "\n".join(parts)

        lines = []
        must = beat.get("must", [])
        if must:
            lines.append("Debe incluir:")
            lines.extend(f"- {m}" for m in must)
        must_not = beat.get("must_not", [])
        if must_not:
            lines.append("No debe incluir:")
            lines.extend(f"- {m}" for m in must_not)
        sc = beat.get("state_change", {})
        if sc:
            lines.append(f"Transición emocional: {sc.get('from', '')} → {sc.get('to', '')}")
        success = beat.get("success_signal", [])
        if success:
            lines.append(f"Señal de éxito: {success[0]}")
        return "\n".join(lines)
