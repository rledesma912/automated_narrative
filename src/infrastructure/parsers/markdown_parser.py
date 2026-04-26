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
    # Spec-043: campos enriquecidos (opcionales, retrocompatibles)
    storyteller_config: dict = field(default_factory=dict)
    typed_rules: list[dict] = field(default_factory=list)
    structured_synopsis: dict = field(default_factory=dict)
    rich_scenarios: list[dict] = field(default_factory=list)
    personajes_full: list[dict] = field(default_factory=list)


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

        # Buscar frontmatter con cierre (--- content ---) o solo con apertura (--- content)
        frontmatter_match = re.search(
            r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL | re.MULTILINE
        )
        yaml_body: str | None = None
        if frontmatter_match:
            yaml_body = frontmatter_match.group(1)
        elif content.startswith("---"):
            # Archivo con apertura --- pero sin cierre: tratar todo el contenido (sin la línea ---) como YAML
            yaml_body = re.sub(r"^---\s*\n", "", content, count=1)

        if yaml_body is not None:
            try:
                raw_frontmatter = self._sanitize_frontmatter(yaml_body)
                data = yaml.safe_load(raw_frontmatter)

                # --- story block (nuevo formato: story.title) o campo directo ---
                story_block = data.get("story") or {}
                title = story_block.get("title") or data.get("title", file_path.stem)

                # --- protagonists: lista de objetos con id/name/role ---
                protagonists = data.get("protagonists") or []

                # --- storyteller: puede ser {id: P1} o string directo ---
                storyteller_raw = data.get("storyteller") or data.get("relator", "")
                if isinstance(storyteller_raw, dict):
                    st_id = storyteller_raw.get("id", "")
                    match = next((p for p in protagonists if p.get("id") == st_id), None)
                    storyteller = match["name"] if match else st_id
                else:
                    storyteller = str(storyteller_raw)

                # --- protagonista: role=protagonista en lista, fallback a campo directo ---
                protagonista = ""
                if protagonists:
                    prot_match = next(
                        (p for p in protagonists if p.get("role") == "protagonista"), None
                    )
                    protagonista = prot_match["name"] if prot_match else protagonists[0].get("name", "")
                if not protagonista:
                    protagonista = data.get("protagonist") or data.get("protagonista", "")

                # --- elenco completo: nombre + rol de cada personaje ---
                personajes_full = [
                    {"name": p.get("name", ""), "role": p.get("role", "")}
                    for p in protagonists
                    if p.get("name")
                ]

                # --- storyteller_config ---
                storyteller_config = data.get("storyteller_config") or {}
                if not isinstance(storyteller_config, dict):
                    storyteller_config = {}

                # --- rules: lista de dicts (nuevo) o lista de strings (legado) ---
                raw_rules = data.get("rules") or data.get("reglas") or []
                typed_rules: list[dict] = []
                reglas: list[str] = []
                if raw_rules and isinstance(raw_rules[0], dict):
                    for r in raw_rules:
                        typed_rules.append({
                            "id": r.get("id", ""),
                            "content": r.get("text", r.get("content", "")),
                            "type": r.get("type"),
                            "intensity": r.get("intensity"),
                        })
                        reglas.append(r.get("text", r.get("content", "")))
                else:
                    reglas = [str(r) for r in raw_rules if r]

                # --- synopsis: dict act_1..act_N (nuevo) o string directo (legado) ---
                raw_synopsis = data.get("synopsis") or data.get("sinopsis") or ""
                structured_synopsis: dict = {}
                if isinstance(raw_synopsis, dict):
                    structured_synopsis = raw_synopsis
                    sinopsis = "\n\n".join(
                        v.get("text", "").strip()
                        for v in raw_synopsis.values()
                        if isinstance(v, dict) and v.get("text")
                    )
                else:
                    sinopsis = str(raw_synopsis)

                # --- scenarios: lista de dicts (nuevo) o legado ---
                raw_scenarios = data.get("scenarios") or data.get("escenarios")
                rich_scenarios: list[dict] = []
                cronologic_scenarios: list[str] = []

                if isinstance(raw_scenarios, list) and raw_scenarios and isinstance(raw_scenarios[0], dict):
                    sorted_sc = sorted(raw_scenarios, key=lambda s: s.get("order", s.get("id", 0)))
                    for s in sorted_sc:
                        rich_scenarios.append(s)
                        cronologic_scenarios.append(s.get("name", ""))
                elif isinstance(raw_scenarios, list):
                    cronologic_scenarios = [str(s).strip() for s in raw_scenarios if s]
                elif isinstance(raw_scenarios, str):
                    cronologic_scenarios = [s.strip() for s in raw_scenarios.split("/") if s.strip()]

                # Fallback cronologic_scenarios al campo explícito si existe
                if not cronologic_scenarios:
                    cronologic_scenarios = self._parse_cronologic_scenarios(data)

                atmosfera_block = data.get("atmosphere") or data.get("atmosfera") or {}
                if isinstance(atmosfera_block, dict):
                    atmosfera = atmosfera_block.get("tone") or atmosfera_block.get("genre") or ""
                else:
                    atmosfera = str(atmosfera_block)

                result = MarkdownStoryData(
                    title=title,
                    protagonista=protagonista,
                    relator=self._normalize_relator(storyteller),
                    sinopsis=sinopsis,
                    atmosfera=atmosfera,
                    reglas=reglas,
                    cronologic_scenarios=cronologic_scenarios,
                    storyteller_config=storyteller_config,
                    typed_rules=typed_rules,
                    structured_synopsis=structured_synopsis,
                    rich_scenarios=rich_scenarios,
                    personajes_full=personajes_full,
                )
                logger.debug(
                    "[Parser] YAML frontmatter extraído: title=%r, relator=%r, "
                    "protagonista=%r, atmosfera=%r, sinopsis=%r..., reglas=%d, typed=%d",
                    result.title, result.relator, result.protagonista[:40],
                    result.atmosfera[:40], result.sinopsis[:60],
                    len(result.reglas), len(result.typed_rules),
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
