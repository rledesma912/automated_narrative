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
    """Datos extraídos del markdown (Normalizado)."""

    title: str
    protagonista: str
    relator: str
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
                
                # Resolución de escenarios: preferir cronologic_scenarios
                scenarios = self._parse_cronologic_scenarios(data)
                if not scenarios:
                    # Fallback a 'scenarios' o 'escenarios' (intentar parsear como lista o split por /)
                    legacy = data.get("scenarios") or data.get("escenarios")
                    if isinstance(legacy, list):
                        scenarios = [str(s).strip() for s in legacy]
                    elif isinstance(legacy, str):
                        scenarios = [s.strip() for s in legacy.split("/") if s.strip()]

                result = MarkdownStoryData(
                    title=data.get("title", file_path.stem),
                    protagonista=data.get("protagonist") or data.get("protagonista", ""),
                    relator=self._normalize_relator(storyteller),
                    sinopsis=data.get("sinopsis") or data.get("synopsis", ""),
                    atmosfera=data.get("atmosphere") or data.get("atmosfera", ""),
                    reglas=data.get("reglas") or data.get("rules", []),
                    cronologic_scenarios=scenarios,
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
                    "Usando fallback regex.",
                    file_path.name, e,
                )

        result = self._extract_data_via_regex(content, file_path.stem)
        self._validate(result, file_path.name)
        return result

    def _extract_data_via_regex(self, content: str, default_title: str) -> MarkdownStoryData:
        """Extrae los campos del contenido usando expresiones regulares."""
        raw_protagonista = self._extract_inline_field(content, "Protagonistas")
        raw_sinopsis = self._extract_inline_field(content, "Sinopsis")
        raw_atmosfera = self._extract_inline_field(content, "Atmósfera") or self._extract_inline_field(content, "Atmosfera")

        raw_relator = self._extract_inline_field(content, "relator")
        relator = raw_relator.split()[0] if raw_relator else "tercera_persona"

        # Escenarios: intentar extraer como sección de lista
        scenarios = self._extract_list(content, "Escenarios")
        if not scenarios:
            # Intentar campo inline con /
            raw_escenarios = self._extract_inline_field(content, "Escenarios")
            if raw_escenarios:
                scenarios = [s.strip() for s in raw_escenarios.split("/") if s.strip()]

        reglas = self._extract_list(content, "Las reglas de la historia") or self._extract_list(content, "Reglas")

        return MarkdownStoryData(
            title=default_title,
            protagonista=raw_protagonista.strip(),
            relator=self._normalize_relator(relator),
            sinopsis=raw_sinopsis.strip(),
            atmosfera=raw_atmosfera.strip(),
            reglas=reglas,
            cronologic_scenarios=scenarios,
        )

    def _extract_inline_field(self, content: str, field_name: str) -> str:
        """Extrae campo en formato **Campio**: valor."""
        pattern = (
            rf"\*\*{re.escape(field_name)}\*\*:\s*(.+?)(?=\n\s*\n|\n\s*-|\n\s*\*\*|\n\s*---|$)"
        )
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
        """Normaliza relator."""
        relator_lower = str(relator).lower().strip()
        if "tercera" in relator_lower or "3" in relator_lower: return "tercera_persona"
        if "primera" in relator_lower or "1" in relator_lower: return "primera_persona"
        if "segunda" in relator_lower or "2" in relator_lower: return "segunda_persona"
        return relator.strip()

    def _sanitize_frontmatter(self, raw: str) -> str:
        """Limpia frontmatter para bloques literales."""
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
        """Extrae lista de escenarios del frontmatter."""
        value = data.get("cronologic_scenarios")
        if isinstance(value, list):
            return [str(item).strip().lstrip("- ") for item in value if item]
        if isinstance(value, str):
            items = []
            for line in value.splitlines():
                line = line.strip().lstrip("- ").strip()
                if line: items.append(line)
            return items
        return []

    def _validate(self, data: "MarkdownStoryData", source: str) -> None:
        """Validación de campos obligatorios."""
        missing = []
        if not data.title: missing.append("title")
        if not data.protagonista: missing.append("protagonista")
        if not data.sinopsis: missing.append("sinopsis")
        if not data.cronologic_scenarios: missing.append("escenarios")
        if missing:
            raise ValueError(f"[Parser] Campos faltantes en '{source}': {', '.join(missing)}")
