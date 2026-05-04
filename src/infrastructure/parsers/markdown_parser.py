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
        """Parsea un archivo markdown o YAML y extrae los datos."""
        clean_filename = Path(filename).name
        file_path = self.input_dir / clean_filename

        if not file_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        content = file_path.read_text(encoding="utf-8")

        # Detección del cuerpo YAML:
        # 1) Archivos `.yaml`/`.yml` puros → todo el contenido es YAML
        # 2) Markdown con frontmatter `--- ... ---` → extraer el bloque
        # 3) Markdown que abre con `---` sin cierre → tratar el resto como YAML
        yaml_body: str | None = None
        suffix = file_path.suffix.lower()
        if suffix in (".yaml", ".yml"):
            yaml_body = content
        else:
            frontmatter_match = re.search(
                r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL | re.MULTILINE
            )
            if frontmatter_match:
                yaml_body = frontmatter_match.group(1)
            elif content.startswith("---"):
                yaml_body = re.sub(r"^---\s*\n", "", content, count=1)

        if yaml_body is not None:
            try:
                raw_frontmatter = self._sanitize_frontmatter(yaml_body)
                data = yaml.safe_load(raw_frontmatter)
                if not isinstance(data, dict):
                    raise ValueError("YAML root no es un mapping")

                result = self._build_from_yaml(data, file_path.stem)
                logger.debug(
                    "[Parser] YAML frontmatter extraído: title=%r, relator=%r, "
                    "protagonista=%r, atmosfera=%r, sinopsis=%r..., reglas=%d, typed=%d",
                    result.title,
                    result.relator,
                    result.protagonista[:40],
                    result.atmosfera[:40],
                    result.sinopsis[:60],
                    len(result.reglas),
                    len(result.typed_rules),
                )
                self._validate(result, file_path.name)
                return result
            except yaml.YAMLError as e:
                logger.warning(
                    "[Parser] YAML inválido en frontmatter de '%s': %s. Usando fallback regex.",
                    file_path.name,
                    e,
                )

        result = self._extract_data_via_regex(content, file_path.stem)
        self._validate(result, file_path.name)
        return result

    # ── Construcción desde YAML canónico (Spec-217) ──────────────────────────

    def _build_from_yaml(self, data: dict, default_title: str) -> MarkdownStoryData:
        """Construye MarkdownStoryData desde el YAML canónico Spec-217.

        Soporta también el formato viejo (story.title, protagonists, synopsis dict)
        con detección automática.
        """
        # Título: top-level → story.title → stem del archivo
        story_block = data.get("story") or {}
        title = data.get("title") or story_block.get("title") or default_title

        # Personajes: preferir top-level personajes_full (canónico), fallback a protagonists
        raw_personajes = data.get("personajes_full") or data.get("protagonists") or []
        personajes_full: list[dict] = []
        for idx, p in enumerate(raw_personajes, start=1):
            if not p or not p.get("name"):
                continue
            personajes_full.append(
                {
                    "id": p.get("id") or f"P{idx}",
                    "name": p.get("name", ""),
                    "role": p.get("role", ""),
                    "traits": list(p.get("traits") or []),
                }
            )

        # storyteller_config: si viene como bloque rico, normalizar; si no, reconstruir
        sc_raw = data.get("storyteller_config") or {}
        if not isinstance(sc_raw, dict):
            sc_raw = {}
        storyteller_config = self._normalize_storyteller_config(sc_raw, data, personajes_full)

        # typed_rules: derivar de storyteller_config.rules (formato canónico) si existen,
        # si no, del bloque legado data["rules"]
        typed_rules: list[dict] = []
        reglas: list[str] = []
        sc_rules = storyteller_config.get("rules") or []
        if sc_rules:
            for r in sc_rules:
                text = r.get("text", "")
                typed_rules.append(
                    {
                        "id": r.get("id", ""),
                        "content": text,
                        "type": r.get("type") or None,
                        "intensity": r.get("intensity"),
                    }
                )
                if text:
                    reglas.append(text)
        else:
            raw_rules = data.get("rules") or data.get("reglas") or []
            if raw_rules and isinstance(raw_rules[0], dict):
                for r in raw_rules:
                    text = r.get("text", r.get("content", ""))
                    typed_rules.append(
                        {
                            "id": r.get("id", ""),
                            "content": text,
                            "type": r.get("type"),
                            "intensity": r.get("intensity"),
                        }
                    )
                    if text:
                        reglas.append(text)
            else:
                reglas = [str(r) for r in raw_rules if r]

        # Backward-compat: top-level reglas[] tiene prioridad si está
        top_reglas = data.get("reglas")
        if isinstance(top_reglas, list) and top_reglas and isinstance(top_reglas[0], str):
            reglas = [str(r) for r in top_reglas if r]

        # Sinopsis: top-level → composición desde actos → vacío
        sinopsis = (
            (data.get("sinopsis") or "").strip() if isinstance(data.get("sinopsis"), str) else ""
        )
        if not sinopsis:
            actos = storyteller_config.get("actos") or {}
            sinopsis = "\n\n".join(
                v.get("text", "").strip()
                for k in ("act_1", "act_2", "act_3", "act_4", "act_5")
                for v in [actos.get(k)]
                if isinstance(v, dict) and v.get("text")
            )
        if not sinopsis:
            # Último fallback: synopsis legado
            raw_syn = data.get("synopsis") or ""
            if isinstance(raw_syn, dict):
                sinopsis = "\n\n".join(
                    v.get("text", "").strip()
                    for v in raw_syn.values()
                    if isinstance(v, dict) and v.get("text")
                )
            else:
                sinopsis = str(raw_syn)

        # Escenarios cronológicos: top-level escenarios → storyteller_config.scenarios → legado
        cronologic_scenarios = self._derive_cronologic_scenarios(data, storyteller_config)

        # structured_synopsis y rich_scenarios: derivados retrocompatibles
        structured_synopsis = storyteller_config.get("actos") or {}
        rich_scenarios = list(storyteller_config.get("scenarios") or [])

        # Atmósfera (string backward-compat): top-level → composición desde atmosphere
        atmosfera = self._derive_atmosfera(data, storyteller_config)

        # Protagonista (string backward-compat): top-level → composición desde personajes
        protagonista = self._derive_protagonista(data, personajes_full)

        # Relator (string backward-compat): top-level → composición desde storyteller
        relator = self._derive_relator(data, storyteller_config, personajes_full)

        return MarkdownStoryData(
            title=title,
            protagonista=protagonista,
            relator=relator,
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

    def _normalize_storyteller_config(
        self, sc: dict, data: dict, personajes_full: list[dict]
    ) -> dict:
        """Garantiza que storyteller_config tenga todas las keys que mapStoryToWizard() espera.

        Si una key falta, intenta derivarla de otros campos del YAML o usar defaults.
        """
        st_id = sc.get("storyteller_id") or (personajes_full[0]["id"] if personajes_full else "P1")
        st_name = sc.get("storyteller_name")
        if not st_name and personajes_full:
            match = next((p for p in personajes_full if p["id"] == st_id), personajes_full[0])
            st_name = match.get("name", "")

        voice = sc.get("voice") or {}
        voice_style = sc.get("voice_style") or voice.get("style") or "intimista"

        atmosphere = sc.get("atmosphere") or {}
        # Si atmosphere viene como string en data["atmosphere"] (formato legado), parsear
        if not atmosphere and isinstance(data.get("atmosphere"), dict):
            atmosphere = data["atmosphere"]

        scenarios = self._normalize_scenarios(sc.get("scenarios"), data)
        rules = self._normalize_rules(sc.get("rules"), data)
        actos = self._normalize_actos(sc.get("actos"), data)

        perception = sc.get("perception") or {}
        distortion = perception.get("distortion") or {}
        knowledge = sc.get("knowledge") or {}
        domain = knowledge.get("domain") or {}
        language = sc.get("language") or {}
        bias = sc.get("bias") or {}

        return {
            "storyteller_id": st_id,
            "storyteller_name": st_name or "",
            "voice_style": voice_style,
            "voice": {
                "person": voice.get("person", "primera"),
                "tense": voice.get("tense", "pasado"),
                "style": voice.get("style") or voice_style,
            },
            "atmosphere": {
                "genre": atmosphere.get("genre", ""),
                "subgenre": atmosphere.get("subgenre", ""),
                "tone": atmosphere.get("tone", ""),
            },
            "scenarios": scenarios,
            "rules": rules,
            "actos": actos,
            "perception": {
                "reliability": perception.get("reliability", "subjetiva"),
                "distortion": {
                    "level": distortion.get("level", "media"),
                    "triggers": list(distortion.get("triggers") or []),
                },
            },
            "knowledge": {
                "domain": {
                    "paranormal": domain.get("paranormal", "medio"),
                    "religioso": domain.get("religioso", "medio"),
                },
                "interpretation_style": knowledge.get("interpretation_style", "simbolica"),
            },
            "language": {
                "register": language.get("register", "coloquial"),
                "figurative_density": language.get("figurative_density", "media"),
            },
            "bias": {
                "fear_focus": list(bias.get("fear_focus") or []),
                "attention_focus": list(bias.get("attention_focus") or []),
            },
        }

    def _normalize_scenarios(self, sc_scenarios: object, data: dict) -> list[dict]:
        """Devuelve la lista canónica de escenarios."""
        source = sc_scenarios
        if not source:
            top = data.get("scenarios")
            if isinstance(top, list) and top and isinstance(top[0], dict):
                source = top
        if isinstance(source, list) and source and isinstance(source[0], dict):
            sorted_sc = sorted(source, key=lambda s: s.get("order", 0))
            return [
                {
                    "id": s.get("id") or f"S{idx}",
                    "order": s.get("order", idx),
                    "name": s.get("name", ""),
                    "description": s.get("description", ""),
                }
                for idx, s in enumerate(sorted_sc, start=1)
            ]
        # Fallback: lista de strings
        names = data.get("scenarios") if isinstance(data.get("scenarios"), list) else []
        return [
            {"id": f"S{idx}", "order": idx, "name": str(n), "description": ""}
            for idx, n in enumerate(names or [], start=1)
        ]

    def _normalize_rules(self, sc_rules: object, data: dict) -> list[dict]:
        """Devuelve la lista canónica de rules con keys id/text/type."""
        source = sc_rules
        if not source:
            top = data.get("rules")
            if isinstance(top, list) and top and isinstance(top[0], dict):
                source = top
        if isinstance(source, list) and source and isinstance(source[0], dict):
            return [
                {
                    "id": r.get("id") or f"R{idx}",
                    "text": r.get("text") or r.get("content", ""),
                    "type": r.get("type") or "",
                }
                for idx, r in enumerate(source, start=1)
            ]
        # Fallback: lista de strings
        raw = data.get("reglas") if isinstance(data.get("reglas"), list) else []
        return [
            {"id": f"R{idx}", "text": str(r), "type": ""}
            for idx, r in enumerate(raw or [], start=1)
        ]

    def _normalize_actos(self, sc_actos: object, data: dict) -> dict:
        """Devuelve el dict canónico de actos act_1..act_5."""
        canonical = [
            ("act_1", "exposicion"),
            ("act_2", "accion_ascendente"),
            ("act_3", "climax"),
            ("act_4", "accion_descendente"),
            ("act_5", "desenlace"),
        ]
        # Preferir storyteller_config.actos; fallback a top-level synopsis (formato legado)
        source = sc_actos if isinstance(sc_actos, dict) else None
        if source is None:
            top = data.get("synopsis")
            if isinstance(top, dict):
                source = top
        out: dict[str, dict] = {}
        for key, default_type in canonical:
            block = source.get(key) if isinstance(source, dict) else None
            if isinstance(block, dict):
                out[key] = {
                    "type": block.get("type") or default_type,
                    "text": block.get("text", ""),
                }
            else:
                out[key] = {"type": default_type, "text": ""}
        return out

    def _derive_cronologic_scenarios(self, data: dict, sc: dict) -> list[str]:
        """Lista de nombres en orden cronológico."""
        scenarios = sc.get("scenarios") or []
        if scenarios:
            return [s.get("name", "") for s in scenarios if s.get("name")]
        # Fallback al campo top-level escenarios string-separado
        raw = data.get("escenarios")
        if isinstance(raw, str) and raw:
            return [chunk.split(":")[0].strip() for chunk in raw.split(";") if chunk.strip()]
        if isinstance(raw, list):
            return [str(s).strip() for s in raw if s]
        return self._parse_cronologic_scenarios(data)

    def _derive_atmosfera(self, data: dict, sc: dict) -> str:
        """String backward-compat de atmósfera."""
        top = data.get("atmosfera")
        if isinstance(top, str) and top:
            return top
        atm = sc.get("atmosphere") or {}
        parts = []
        if atm.get("genre"):
            parts.append(atm["genre"])
        if atm.get("subgenre"):
            parts.append(f"({atm['subgenre']})")
        if atm.get("tone"):
            parts.append(f"- {atm['tone']}")
        return " ".join(parts).strip()

    def _derive_protagonista(self, data: dict, personajes: list[dict]) -> str:
        """String backward-compat del protagonista (puede ser composición de elenco)."""
        top = data.get("protagonista") or data.get("protagonist")
        if isinstance(top, str) and top:
            return top
        if not personajes:
            return ""
        # Composición tipo wizard: "Name: Role [traits]; ..."
        parts = []
        for p in personajes:
            block = f"{p.get('name', '')}: {p.get('role', '')}"
            traits = p.get("traits") or []
            if traits:
                block += f" [{', '.join(traits)}]"
            parts.append(block)
        return "; ".join(parts)

    def _derive_relator(self, data: dict, sc: dict, personajes: list[dict]) -> str:
        """String backward-compat del relator."""
        top = data.get("relator") or data.get("storyteller")
        if isinstance(top, str) and top:
            return top
        # Composición desde sc
        st_id = sc.get("storyteller_id", "P1")
        st_name = sc.get("storyteller_name") or next(
            (p["name"] for p in personajes if p["id"] == st_id), ""
        )
        voice_style = sc.get("voice_style") or sc.get("voice", {}).get("style", "")
        register = sc.get("language", {}).get("register", "")
        return f"Primera persona en pasado. Narrador: {st_name}. Tono: {voice_style}. Registro: {register}.".strip()

    def _extract_data_via_regex(self, content: str, default_title: str) -> MarkdownStoryData:
        """Extrae los campos del contenido usando expresiones regulares."""
        raw_protagonista = self._extract_inline_field(content, "Protagonistas")
        raw_sinopsis = self._extract_inline_field(content, "Sinopsis")
        raw_atmosfera = self._extract_inline_field(
            content, "Atmósfera"
        ) or self._extract_inline_field(content, "Atmosfera")

        raw_relator = self._extract_inline_field(content, "relator")
        relator = raw_relator.split()[0] if raw_relator else "tercera_persona"

        # Escenarios: intentar extraer como sección de lista
        scenarios = self._extract_list(content, "Escenarios")
        if not scenarios:
            # Intentar campo inline con /
            raw_escenarios = self._extract_inline_field(content, "Escenarios")
            if raw_escenarios:
                scenarios = [s.strip() for s in raw_escenarios.split("/") if s.strip()]

        reglas = self._extract_list(content, "Las reglas de la historia") or self._extract_list(
            content, "Reglas"
        )

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
        if "tercera" in relator_lower or "3" in relator_lower:
            return "tercera_persona"
        if "primera" in relator_lower or "1" in relator_lower:
            return "primera_persona"
        if "segunda" in relator_lower or "2" in relator_lower:
            return "segunda_persona"
        return relator.strip()

    def _sanitize_frontmatter(self, raw: str) -> str:
        """Limpia frontmatter para bloques literales."""
        lines = raw.split("\n")
        result = []
        for line in lines:
            match = re.match(r"^(\s*[\w][\w\s]*?):\s*[|>]\s+(.+)$", line)
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
                if line:
                    items.append(line)
            return items
        return []

    def _validate(self, data: "MarkdownStoryData", source: str) -> None:
        """Validación de campos obligatorios."""
        missing = []
        if not data.title:
            missing.append("title")
        if not data.protagonista:
            missing.append("protagonista")
        if not data.sinopsis:
            missing.append("sinopsis")
        if not data.cronologic_scenarios:
            missing.append("escenarios")
        if missing:
            raise ValueError(f"[Parser] Campos faltantes en '{source}': {', '.join(missing)}")
