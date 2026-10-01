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

    def fragment(self, name: str, **data: object) -> str:
        """Una sección del prompt desde `fragments/<name>.md`, con sus datos (Spec-620).

        A diferencia de `load()`, no hace `strip()`: quita solo el salto de línea final del
        archivo, así la sección conserva los que necesita (`\\n\\n` para cerrar un bloque se
        escribe como una línea en blanco al final). Un archivo o un dato que falta es un error:
        un prompt nunca sale con una sección vacía o un `{placeholder}` sin llenar.
        """
        key = f"fragments/{name}.md"
        if key not in self._cache:
            path = self._dir / key
            if not path.exists():
                raise FileNotFoundError(f"Fragmento de prompt inexistente: {key}")
            self._cache[key] = path.read_text(encoding="utf-8").removesuffix("\n")
        return self._cache[key].format(**data)
