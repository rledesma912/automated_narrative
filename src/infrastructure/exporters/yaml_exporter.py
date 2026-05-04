"""YamlStoryExporter — vuelca un Story al formato YAML canónico (Spec-217).

El YAML producido es input válido del comando `generate --input` (round-trip
bidireccional) y refleja 1:1 la estructura interna de `storyteller_config`
que `mapStoryToWizard()` consume para rehidratar el wizard del frontend.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from src.domain.models import Story

logger = logging.getLogger(__name__)


class _LiteralStr(str):
    """str que se serializa con bloque literal '|' (preserva newlines)."""


def _literal_representer(dumper: yaml.Dumper, data: _LiteralStr) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style="|")


yaml.add_representer(_LiteralStr, _literal_representer, Dumper=yaml.SafeDumper)


class YamlStoryExporter:
    """Serializa un Story al formato YAML canónico Spec-217."""

    def export(self, story: Story) -> str:
        """Devuelve el YAML como string."""
        doc = self._build_document(story)
        return yaml.safe_dump(
            doc,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=100,
            indent=2,
        )

    def export_to_file(self, story: Story, path: Path) -> Path:
        """Escribe el YAML al path indicado y retorna el path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.export(story), encoding="utf-8")
        return path

    # ── Construcción del documento ───────────────────────────────────────────

    def _build_document(self, story: Story) -> dict[str, Any]:
        sc = story.storyteller_config or {}
        personajes = self._build_personajes(story)

        return {
            "title": story.title,
            "personajes_full": personajes,
            "protagonista": story.protagonista,
            "relator": story.relator,
            "atmosfera": story.atmosfera,
            "escenarios": self._derive_escenarios_str(sc, story),
            "sinopsis": _LiteralStr(story.sinopsis or ""),
            "reglas": list(story.reglas or []),
            "storyteller_config": self._build_storyteller_config(sc, story),
        }

    def _build_personajes(self, story: Story) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for idx, p in enumerate(story.personajes_full or [], start=1):
            out.append(
                {
                    "id": p.get("id") or f"P{idx}",
                    "name": p.get("name", ""),
                    "role": p.get("role", ""),
                    "traits": list(p.get("traits") or []),
                }
            )
        return out

    def _derive_escenarios_str(self, sc: dict, story: Story) -> str:
        scenarios = sc.get("scenarios") or []
        if scenarios:
            parts = []
            for s in scenarios:
                name = s.get("name", "")
                desc = s.get("description", "")
                parts.append(f"{name}: {desc}" if desc else name)
            return "; ".join(parts)
        if story.scenarios:
            return "; ".join(s.name for s in story.scenarios)
        return ""

    def _build_storyteller_config(self, sc: dict, story: Story) -> dict[str, Any]:
        """Reconstruye el bloque canónico, completando lo que falte desde Story."""
        scenarios = self._build_scenarios(sc, story)
        rules = self._build_rules(sc, story)
        actos = self._build_actos(sc)

        return {
            "storyteller_id": sc.get("storyteller_id") or "P1",
            "storyteller_name": sc.get("storyteller_name") or "",
            "voice_style": sc.get("voice_style") or sc.get("voice", {}).get("style") or "intimista",
            "voice": {
                "person": sc.get("voice", {}).get("person", "primera"),
                "tense": sc.get("voice", {}).get("tense", "pasado"),
                "style": sc.get("voice", {}).get("style") or sc.get("voice_style") or "intimista",
            },
            "atmosphere": {
                "genre": sc.get("atmosphere", {}).get("genre", ""),
                "subgenre": sc.get("atmosphere", {}).get("subgenre", ""),
                "tone": sc.get("atmosphere", {}).get("tone", ""),
            },
            "scenarios": scenarios,
            "rules": rules,
            "actos": actos,
            "perception": {
                "reliability": sc.get("perception", {}).get("reliability", "subjetiva"),
                "distortion": {
                    "level": sc.get("perception", {}).get("distortion", {}).get("level", "media"),
                    "triggers": list(
                        sc.get("perception", {}).get("distortion", {}).get("triggers") or []
                    ),
                },
            },
            "knowledge": {
                "domain": {
                    "paranormal": sc.get("knowledge", {})
                    .get("domain", {})
                    .get("paranormal", "medio"),
                    "religioso": sc.get("knowledge", {})
                    .get("domain", {})
                    .get("religioso", "medio"),
                },
                "interpretation_style": sc.get("knowledge", {}).get(
                    "interpretation_style", "simbolica"
                ),
            },
            "language": {
                "register": sc.get("language", {}).get("register", "coloquial"),
                "figurative_density": sc.get("language", {}).get("figurative_density", "media"),
            },
            "bias": {
                "fear_focus": list(sc.get("bias", {}).get("fear_focus") or []),
                "attention_focus": list(sc.get("bias", {}).get("attention_focus") or []),
            },
        }

    def _build_scenarios(self, sc: dict, story: Story) -> list[dict[str, Any]]:
        rich = sc.get("scenarios") or []
        if rich:
            out = []
            for idx, s in enumerate(rich, start=1):
                out.append(
                    {
                        "id": s.get("id") or f"S{idx}",
                        "order": s.get("order", idx),
                        "name": s.get("name", ""),
                        "description": s.get("description", ""),
                    }
                )
            return out
        # Fallback: derivar desde story.scenarios (sin description)
        return [
            {"id": f"S{i}", "order": i, "name": s.name, "description": ""}
            for i, s in enumerate(story.scenarios or [], start=1)
        ]

    def _build_rules(self, sc: dict, story: Story) -> list[dict[str, Any]]:
        rich = sc.get("rules") or []
        if rich:
            out = []
            for idx, r in enumerate(rich, start=1):
                out.append(
                    {
                        "id": r.get("id") or f"R{idx}",
                        "text": r.get("text") or r.get("content", ""),
                        "type": r.get("type") or "",
                    }
                )
            return out
        # Fallback: typed_rules
        if story.typed_rules:
            out = []
            for idx, r in enumerate(story.typed_rules, start=1):
                rule_type = r.type.value if hasattr(r.type, "value") and r.type else (r.type or "")
                out.append(
                    {
                        "id": r.id or f"R{idx}",
                        "text": r.content,
                        "type": rule_type,
                    }
                )
            return out
        # Último fallback: reglas como strings
        return [
            {"id": f"R{i}", "text": txt, "type": ""}
            for i, txt in enumerate(story.reglas or [], start=1)
        ]

    def _build_actos(self, sc: dict) -> dict[str, dict[str, Any]]:
        actos_raw = sc.get("actos") or {}
        canonical_keys = [
            ("act_1", "exposicion"),
            ("act_2", "accion_ascendente"),
            ("act_3", "climax"),
            ("act_4", "accion_descendente"),
            ("act_5", "desenlace"),
        ]
        out: dict[str, dict[str, Any]] = {}
        for key, default_type in canonical_keys:
            block = actos_raw.get(key) or {}
            text = block.get("text", "") if isinstance(block, dict) else str(block)
            out[key] = {
                "type": (block.get("type") if isinstance(block, dict) else None) or default_type,
                "text": _LiteralStr(text) if text else "",
            }
        return out
