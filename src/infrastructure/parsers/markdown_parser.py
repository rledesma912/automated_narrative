"""MarkdownStoryParser - parser para archivos de historia markdown con soporte Frontmatter."""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class MarkdownStoryData:
    """Datos extraídos del markdown."""

    title: str
    protagonista: str
    relator: str
    escenarios: str
    sinopsis: str
    atmosfera: str = ""
    reglas: list[str] = field(default_factory=list)
    cronologic_scenarios: list[str] = field(default_factory=list)


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
                raw_frontmatter = self._sanitize_frontmatter(frontmatter_match.group(1))
                data = yaml.safe_load(raw_frontmatter)
                storyteller = data.get("storyteller") or data.get("relator", "")
                result = MarkdownStoryData(
                    title=data.get("title", file_path.stem),
                    protagonista=data.get("protagonist") or data.get("protagonista", ""),
                    relator=self._normalize_relator(storyteller),
                    escenarios=self._resolve_escenarios(data),
                    sinopsis=data.get("sinopsis") or data.get("synopsis", ""),
                    atmosfera=data.get("atmosphere") or data.get("atmosfera", ""),
                    reglas=data.get("reglas") or data.get("rules", []),
                    cronologic_scenarios=self._parse_cronologic_scenarios(data),
                )
                logger.debug(
                    "[Parser] YAML frontmatter extraído: title=%r, relator=%r, "
                    "protagonista=%r, atmosfera=%r, sinopsis=%r..., reglas=%d",
                    result.title, result.relator, result.protagonista[:40],
                    result.atmosfera[:40], result.sinopsis[:60], len(result.reglas),
                )
                self._validate(result, file_path.name)
                return result
            except yaml.YAMLError as e:
                logger.warning(
                    "[Parser] YAML inválido en frontmatter de '%s': %s. "
                    "Usando fallback regex. Verificar formato del archivo.",
                    file_path.name, e,
                )

        result = self._extract_data_via_regex(content, file_path.stem)
        self._validate(result, file_path.name)
        return result

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
        """Normaliza relator a valores válidos.

        Mantiene nombres de personajes específicos (Irene, Ricardo, etc.)
        que no sean valores estándar.
        """
        relator_lower = str(relator).lower().strip()

        if "tercera" in relator_lower or "3" in relator_lower:
            return "tercera_persona"
        if "primera" in relator_lower or "1" in relator_lower:
            return "primera_persona"
        if "segunda" in relator_lower or "2" in relator_lower:
            return "segunda_persona"

        if relator_lower in ("primera_persona", "tercera_persona", "segunda_persona"):
            return relator_lower

        return relator.strip()

    def _sanitize_frontmatter(self, raw: str) -> str:
        """Convierte 'key: | texto en misma línea' a bloque YAML válido."""
        lines = raw.split("\n")
        result = []
        for line in lines:
            match = re.match(r'^(\s*[\w][\w\s]*?):\s*[|>]\s+(.+)$', line)
            if match:
                result.append(f"{match.group(1)}: |")
                result.append(f"  {match.group(2)}")
            else:
                result.append(line)
        return "\n".join(result)

    def _parse_cronologic_scenarios(self, data: dict) -> list[str]:
        """Devuelve la lista de escenarios cronológicos del frontmatter.

        Acepta tanto YAML list como bloque literal `|` con ítems `- nombre`.
        """
        value = data.get("cronologic_scenarios")
        if isinstance(value, list):
            return [str(item).strip().lstrip("- ") for item in value if item]
        if isinstance(value, str):
            items = []
            for line in value.splitlines():
                line = line.strip().lstrip("- ").strip()
                if line:
                    items.append(line)
            return items
        return []

    def _resolve_escenarios(self, data: dict) -> str:
        """Lee escenarios del frontmatter. Acepta `escenarios`, `scenarios` y `cronologic_scenarios`."""
        value = data.get("escenarios") or data.get("scenarios")
        if value:
            return str(value).strip()
        cronologic = data.get("cronologic_scenarios")
        if isinstance(cronologic, list):
            return " / ".join(item.strip().lstrip("- ") for item in cronologic if item)
        if isinstance(cronologic, str):
            return cronologic.strip()
        return ""

    def _validate(self, data: "MarkdownStoryData", source: str) -> None:
        """Lanza ValueError si faltan campos obligatorios tras el parseo."""
        missing = []
        if not data.title:
            missing.append("title")
        if not data.protagonista:
            missing.append("protagonist / protagonista")
        if not data.sinopsis:
            missing.append("synopsis / sinopsis")
        if missing:
            raise ValueError(
                f"[Parser] Campos obligatorios faltantes en '{source}': "
                f"{', '.join(missing)}. Verificar formato del archivo de input."
            )

    # Alias for backwards compatibility
    _extract_data = _extract_data_via_regex
