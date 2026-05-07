"""YAML story loader."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from src.application.dto import StoryCreateDTO
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
            StoryCreateDTO con los datos del YAML.

        Raises:
            YamlStoryLoaderError: Si el archivo no existe o es inválido.
        """
        if not path.is_absolute():
            candidates = [path, Path(settings.input_dir) / path]
            for candidate in candidates:
                if candidate.exists():
                    path = candidate
                    break
            else:
                raise YamlStoryLoaderError(f"Archivo no encontrado. Buscado en: {candidates}")

        if not path.exists():
            raise YamlStoryLoaderError(f"Archivo no encontrado: {path}")

        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise YamlStoryLoaderError(f"YAML inválido: {e}")

        if data is None:
            raise YamlStoryLoaderError(f"YAML vacío en: {path}")

        return self.load_from_dict(data)

    def load_from_dict(self, data: dict) -> StoryCreateDTO:
        """Convierte un dict parseado de YAML a DTO.

        Args:
            data: Dict con los datos del YAML.

        Returns:
            StoryCreateDTO con los mapped fields.

        Raises:
            YamlStoryError: Si falta algún campo obligatorio.
        """
        try:
            return StoryCreateDTO(
                title=data.get("title", ""),
                protagonista=data.get("protagonista", ""),
                relator=data.get("relator", "tercera_persona"),
                sinopsis=data.get("sinopsis", ""),
                atmosfera=data.get("atmosfera", ""),
                escenarios=self._extract_escenarios(data),
                reglas=data.get("reglas", []),
                personajes_full=data.get("personajes_full", []),
                storyteller_config=data.get("storyteller_config"),
                typed_rules=self._extract_typed_rules(data),
            )
        except ValidationError as e:
            raise YamlStoryLoaderError(f"Validación de campos: {e}")

    def _extract_escenarios(self, data: dict) -> list[str]:
        """Extrae escenarios de storyteller_config.scenarios[].name.

        Según spec §4.1: escenarios viene de la lista rica en
        storyteller_config, no del string top-level.
        """
        storyteller_config = data.get("storyteller_config")
        if not storyteller_config:
            return []

        scenarios = storyteller_config.get("scenarios", [])
        if not scenarios:
            return []

        return [s.get("name", "") for s in scenarios if s.get("name")]

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
            {"id": r.get("id", ""), "content": r.get("text", ""), "type": r.get("type")}
            for r in rules
            if r.get("text")
        ]
