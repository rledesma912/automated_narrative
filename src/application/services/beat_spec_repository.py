"""BeatSpecRepository — fuente de verdad del YAML de beats en memoria."""

import logging
from pathlib import Path

import yaml

from src.config import settings

logger = logging.getLogger(__name__)


class BeatSpecRepository:
    """Carga y expone el spec de macro-beats desde el YAML de definición.

    Spec-450 §2: las reglas de revelación (`reveal_rules`) dependen del
    `reveal_level` de la entidad principal. Los beats se entregan **resueltos**:
    `must`/`must_not` = fijos + la variante del nivel (o `default` sin nivel, que
    reproduce el texto de antes de Spec-450).
    """

    _REVEAL_KEYS = ("must", "must_not")

    def __init__(self, yaml_path: Path | None = None) -> None:
        self._path = yaml_path or Path(settings.beats_definition_file)
        spec = self._load()
        self._beats: list[dict] = spec.get("macro_beats", [])
        self._exposures: dict[str, dict] = spec.get("entity_exposures", {})

    def _load(self) -> dict:
        if not self._path.exists():
            logger.warning(
                f"[BeatSpecRepository] beats_definition_file no encontrado: {self._path}. "
                "Usando 5 beats vacíos."
            )
            return {"macro_beats": [{"id": i, "name": f"beat_{i}"} for i in range(1, 6)]}
        with self._path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("beats_spec", {})

    @property
    def num_beats(self) -> int:
        return len(self._beats)

    def get_all(self, reveal_level: str | None = None) -> list[dict]:
        return [self._resolve(b, reveal_level) for b in self._beats]

    def get_by_id(self, beat_id: int, reveal_level: str | None = None) -> dict:
        beat = next((b for b in self._beats if b["id"] == beat_id), None)
        return self._resolve(beat, reveal_level) if beat else {}

    def exposure_for(self, beat_id: int, reveal_level: str) -> dict:
        """`{key, show, guide}`: cuánto se muestra de una entidad de ese nivel en el beat."""
        beat = next((b for b in self._beats if b["id"] == beat_id), {})
        key = beat.get("entity_exposure", {}).get(_level_key(reveal_level))
        if not key or key not in self._exposures:
            return {}
        return {"key": key, **self._exposures[key]}

    def _resolve(self, beat: dict, reveal_level: str | None) -> dict:
        resolved = {k: v for k, v in beat.items() if k not in ("reveal_rules", "entity_exposure")}
        rules = beat.get("reveal_rules", {})
        for key in self._REVEAL_KEYS:
            variants = rules.get(key)
            if not variants:
                continue
            extra = variants.get(_level_key(reveal_level), variants["default"])
            resolved[key] = [*beat.get(key, []), *extra]
        return resolved

    def get_word_limit(self, beat_id: int, default: str = "") -> str:
        """Retorna el word_limit configurado en el YAML para este beat."""
        beat = self.get_by_id(beat_id)
        return beat.get("word_limit", default)


def _level_key(reveal_level) -> str:
    """`RevealLevel` o str → clave del YAML. Sin nivel → `default`.

    `str()` de un str-Enum da `RevealLevel.NUNCA` (Python 3.11+), no `nunca`.
    """
    if not reveal_level:
        return "default"
    return getattr(reveal_level, "value", reveal_level)
