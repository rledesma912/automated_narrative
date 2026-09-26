"""TemplateLoader — carga archivos .md del disco con caché y selección de variante."""

import logging
from pathlib import Path

from src.config import settings

logger = logging.getLogger(__name__)


class TemplateLoader:
    """Carga plantillas Markdown desde disco con caché en memoria."""

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self._dir = prompts_dir or Path(settings.prompts_dir)
        self._cache: dict[str, str] = {}

    def load(self, filename: str) -> str:
        if filename not in self._cache:
            file_path = self._dir / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8").strip()
                logger.debug(f"[TemplateLoader] loaded: {filename} ({len(content)} chars)")
                self._cache[filename] = content
            else:
                logger.warning(f"[TemplateLoader] not found: {filename}")
                self._cache[filename] = ""
        return self._cache[filename]
