"""BeatSpecRepository — fuente de verdad del YAML de beats en memoria."""

import logging
from pathlib import Path

import yaml

from src.application.services.structure import (
    DEFAULT_STRUCTURE,
    Estructura,
    validate,
    validate_relocations,
)
from src.config import settings

logger = logging.getLogger(__name__)


class BeatSpecRepository:
    """Carga y expone las estructuras de actos desde el YAML de definición.

    Spec-450 §2: las reglas de revelación (`reveal_rules`) dependen del
    `reveal_level` de la entidad principal. Los beats se entregan **resueltos**:
    `must`/`must_not` = fijos + la variante del nivel (o `default` sin nivel, que
    reproduce el texto de antes de Spec-450).

    Spec-650: el YAML trae varias `estructuras` (largo, corto…); cada consulta dice
    de cuál (por defecto, la larga de siempre).
    """

    _REVEAL_KEYS = ("must", "must_not")

    def __init__(self, yaml_path: Path | None = None) -> None:
        self._path = yaml_path or Path(settings.beats_definition_file)
        spec = self._load()
        self._exposures: dict[str, dict] = spec.get("entity_exposures", {})
        raw = spec.get("estructuras") or {}
        if DEFAULT_STRUCTURE not in raw:
            raise ValueError(f"{self._path}: falta la estructura «{DEFAULT_STRUCTURE}»")
        self._structures: dict[str, Estructura] = {
            sid: validate(sid, data, self._exposures) for sid, data in raw.items()
        }
        validate_relocations(self._structures)

    def _load(self) -> dict:
        if not self._path.exists():
            raise FileNotFoundError(f"beats_definition_file no encontrado: {self._path}")
        with self._path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("beats_spec", {})

    @property
    def structure_ids(self) -> list[str]:
        return list(self._structures)

    def estructura(self, structure: str = DEFAULT_STRUCTURE) -> Estructura:
        """La estructura pedida. Una desconocida es un error, nunca la larga en silencio."""
        if structure not in self._structures:
            raise KeyError(f"Estructura desconocida: {structure!r}")
        return self._structures[structure]

    def get_all(
        self, reveal_level: str | None = None, structure: str = DEFAULT_STRUCTURE
    ) -> list[dict]:
        return [self._resolve(b, reveal_level) for b in self.estructura(structure).actos]

    def get_by_id(
        self, beat_id: int, reveal_level: str | None = None, structure: str = DEFAULT_STRUCTURE
    ) -> dict:
        beat = self.estructura(structure).acto(beat_id)
        return self._resolve(beat, reveal_level) if beat else {}

    def exposure_for(
        self, beat_id: int, reveal_level: str, structure: str = DEFAULT_STRUCTURE
    ) -> dict:
        """`{key, show, guide}`: cuánto se muestra de una entidad de ese nivel en el beat."""
        beat = self.estructura(structure).acto(beat_id)
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

    def get_word_limit(
        self, beat_id: int, default: str = "", structure: str = DEFAULT_STRUCTURE
    ) -> str:
        """Retorna el word_limit configurado en el YAML para este beat."""
        beat = self.get_by_id(beat_id, structure=structure)
        return beat.get("word_limit", default)


def _level_key(reveal_level) -> str:
    """`RevealLevel` o str → clave del YAML. Sin nivel → `default`.

    `str()` de un str-Enum da `RevealLevel.NUNCA` (Python 3.11+), no `nunca`.
    """
    if not reveal_level:
        return "default"
    return getattr(reveal_level, "value", reveal_level)
