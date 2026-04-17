"""MarkdownStoryParser - parser para archivos de historia markdown con soporte Frontmatter."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.config import settings


@dataclass
class MarkdownStoryData:
    """Datos extraídos del markdown."""

    title: str
    protagonista: str
    relator: str
    escenarios: str
    sinopsis: str
    reglas: list[str] = field(default_factory=list)


class MarkdownStoryParser:
    """Parser para archivos de historia markdown con soporte para YAML Frontmatter."""

    def __init__(self, input_dir: Path | None = None):
        self.input_dir = input_dir or Path(settings.input_dir)

    def parse(self, filename: str) -> MarkdownStoryData:
        """Parsea un archivo markdown y extrae los datos."""
        clean_filename = Path(filename).name
        file_path = self.input_dir / clean_filename

        if not file_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        content = file_path.read_text(encoding="utf-8")

        frontmatter_match = re.search(
            r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL | re.MULTILINE
        )

        if frontmatter_match:
            try:
                data = yaml.safe_load(frontmatter_match.group(1))
                storyteller = data.get("storyteller") or data.get("relator", "")
                return MarkdownStoryData(
                    title=data.get("title", file_path.stem),
                    protagonista=data.get("protagonist") or data.get("protagonista", ""),
                    relator=self._normalize_relator(storyteller),
                    escenarios=data.get("escenarios") or data.get("scenarios", ""),
                    sinopsis=data.get("sinopsis") or data.get("synopsis", ""),
                    reglas=data.get("reglas") or data.get("rules", []),
                )
            except yaml.YAMLError:
                pass

        return self._extract_data_via_regex(content, file_path.stem)

    def _extract_data_via_regex(self, content: str, default_title: str) -> MarkdownStoryData:
        """Extrae los campos del contenido usando expresiones regulares."""
        raw_protagonista = self._extract_inline_field(content, "Protagonistas")
        raw_escenarios = self._extract_inline_field(content, "Escenarios")
        raw_sinopsis = self._extract_inline_field(content, "Sinopsis")

        raw_relator = self._extract_inline_field(content, "relator")
        relator = raw_relator.split()[0] if raw_relator else "tercera_persona"

        reglas = self._extract_list(content, "Las reglas de la historia")

        return MarkdownStoryData(
            title=default_title,
            protagonista=raw_protagonista.strip(),
            relator=self._normalize_relator(relator),
            escenarios=raw_escenarios.strip(),
            sinopsis=raw_sinopsis.strip(),
            reglas=reglas,
        )

    def _extract_inline_field(self, content: str, field_name: str) -> str:
        """Extrae campo en formato **Campio**: valor."""
        pattern = (
            rf"\*\*{re.escape(field_name)}\*\*:\s*(.+?)(?=\n\s*\n|\n\s*-|\n\s*\*\*|\n\s*---|$)"
        )
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _clean_markdown(self, text: str) -> str:
        """Limpia caracteres de markdown."""
        if not text:
            return text
        cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        cleaned = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", cleaned)
        cleaned = re.sub(r"^#+\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"^\s*-\s+", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"^\s*\*\s+", "", cleaned, flags=re.MULTILINE)
        return cleaned.strip()

    def _extract_field(self, content: str, start: str, end: str) -> str:
        """Extrae texto entre dos marcadores."""
        pattern = re.escape(start) + r"(.*?)" + re.escape(end)
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _extract_list(self, content: str, section: str) -> list[str]:
        """Extrae lista de items de una sección."""
        pattern = re.escape(section) + r"\n(.*?)(?:\n---|\n\s*\*\*|\n#|$)"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if not match:
            return []
        items = re.findall(r"^- (.+)", match.group(1), re.MULTILINE)
        return [item.strip() for item in items]

    def _normalize_relator(self, relator: str) -> str:
        """Normaliza relator a valores válidos."""
        relator_lower = str(relator).lower().strip()
        if "tercera" in relator_lower or "3" in relator_lower:
            return "tercera_persona"
        if "primera" in relator_lower or "1" in relator_lower:
            return "primera_persona"
        if "segunda" in relator_lower or "2" in relator_lower:
            return "segunda_persona"
        return "primera_persona"

    # Alias for backwards compatibility
    _extract_data = _extract_data_via_regex
