"""YAML story loader."""

import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from src.application.dto import StoryCreateDTO
from src.application.services.narrator_config_sanitizer import (
    extract_actos,
    sanitize_narrator_config,
)
from src.config import settings


class YamlStoryLoaderError(Exception):
    """Error loading YAML story."""

    pass


class YamlStoryLoader:
    """Lee un YAML canónico (Spec-217) y produce un StoryCreateDTO.

    Inverso simétrico de YamlStoryExporter. Sin LLM, sin I/O de DB.
    """

    def load_from_file(self, path: Path) -> StoryCreateDTO:
        """Carga un YAML desde archivo y retorna un DTO.

        Args:
            path: Ruta al archivo YAML. Si es relativa, se resuelve contra input_dir.

        Returns:
            StoryCreateDTO con los mapped fields.

        Raises:
            YamlStoryError: Si falta algún campo obligatorio.
        """
        if not path.is_absolute() and not str(path).startswith("input_stories"):
            base = Path(settings.input_dir) if settings.input_dir else Path.cwd()
            path = base / path

        if not path.exists():
            raise YamlStoryLoaderError(f"Archivo no encontrado: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise YamlStoryLoaderError(f"Error parseando YAML: {e}")

        if not data.get("title"):
            raise YamlStoryLoaderError("Falta campo obligatorio: title")

        return self.load_from_dict(data)

    def load_from_dict(self, data: dict) -> StoryCreateDTO:
        """Carga un YAML desde dict y retorna un DTO."""
        try:
            sc = data.get("storyteller_config") or {}
            atmosphere = sc.get("atmosphere") or {}
            legacy_atmosfera = data.get("atmosfera", "")
            genero_top = data.get("genero", "")
            genero, subgenero = self._parse_atmosfera(atmosphere, legacy_atmosfera, genero_top)
            escenarios_full = self._extract_escenarios_full(data)
            actos_full = self._extract_actos(sc)
            return StoryCreateDTO(
                title=data.get("title", ""),
                protagonista=data.get("protagonista", ""),
                relator=data.get("relator", "tercera_persona"),
                sinopsis=data.get("sinopsis", ""),
                genero=genero,
                subgenero=subgenero,
                escenarios=[s["name"] for s in escenarios_full],
                escenarios_full=escenarios_full,
                reglas=data.get("reglas", []),
                personajes_full=_characters(data.get("personajes_full") or []),
                narrator_config=sanitize_narrator_config(data.get("storyteller_config")),
                typed_rules=self._extract_typed_rules(data),
                actos=actos_full,
                entities=list(sc.get("entities") or []),
                **_authoring_fields(data),
            )
        except ValidationError as e:
            raise YamlStoryLoaderError(f"Validación de campos: {e}")

    def load(self, yaml_content: str) -> StoryCreateDTO:
        """Carga un YAML desde string y retorna un DTO."""
        try:
            data = yaml.safe_load(yaml_content) or {}
        except yaml.YAMLError as e:
            raise YamlStoryLoaderError(f"Error parseando YAML: {e}")

        if not data.get("title"):
            raise YamlStoryLoaderError("Falta campo obligatorio: title")

        return self.load_from_dict(data)

    def _extract_escenarios_full(self, data: dict) -> list[dict]:
        """Extrae escenarios (name + description) de storyteller_config.scenarios.

        Según spec §4.1: escenarios viene de la lista rica en
        storyteller_config, no del string top-level. Spec-190 §T6.2: la
        `description` de cada escenario se persiste en la tabla `scenario`.
        """
        storyteller_config = data.get("storyteller_config")
        if not storyteller_config:
            return []

        scenarios = storyteller_config.get("scenarios", [])
        if not scenarios:
            return []

        return [
            {"name": s.get("name", ""), "description": s.get("description", "")}
            for s in scenarios
            if s.get("name")
        ]

    def _extract_typed_rules(self, data: dict) -> list[dict]:
        """Extrae reglas tipadas de storyteller_config.rules[].text -> content.

        Según spec §4.1: typed_rules usa 'content' como clave, no 'text'.
        """
        storyteller_config = data.get("storyteller_config")
        if not storyteller_config:
            return []

        rules = storyteller_config.get("rules", [])
        if not rules:
            return []

        return [
            {
                "id": r.get("id", ""),
                "content": r.get("text", ""),
                "applies_to_beat": r.get("applies_to_beat"),
            }
            for r in rules
            if r.get("text")
        ]

    def _extract_actos(self, storyteller_config: dict) -> list[dict]:
        """Extrae los 5 actos de storyteller_config (ver `extract_actos`)."""
        return extract_actos(storyteller_config)

    def _parse_atmosfera(
        self, atmosphere: dict, legacy_atmosfera: str, genero_top: str = ""
    ) -> tuple[str, str]:
        """`(genero, subgenero)` desde múltiples fuentes.

        Prioridad: genero a nivel superior > atmosphere (genre/subgenre) > campo
        `atmosfera` («genero (subgenero)», con « - tono» en los YAML viejos: el tono
        se ignora, Spec-530 §6).
        """
        if genero_top:
            return genero_top, ""
        genre = atmosphere.get("genre", "")
        if genre:
            return genre, atmosphere.get("subgenre", "")
        match = re.match(r"\s*([^(\-]*?)\s*(?:\(([^)]*)\))?\s*(?:-.*)?$", legacy_atmosfera or "")
        if match:
            return match.group(1), match.group(2) or ""
        return "", ""


# Claves de un personaje que se conservan (`traits` ya no existe, Spec-530 §6).
_CHARACTER_KEYS = ("id", "name", "role", "kind", "relation")


def _characters(raw: list[dict]) -> list[dict]:
    return [{k: p[k] for k in _CHARACTER_KEYS if k in p} for p in raw if isinstance(p, dict)]


def _authoring_fields(data: dict) -> dict:
    """Dirección, taller y escaleta del asistente (Spec-530); ausentes en YAML viejos."""
    return {
        "direction": data.get("direction") or None,
        "workshop": list(data.get("workshop") or []),
        "outline": list(data.get("outline") or []),
    }
