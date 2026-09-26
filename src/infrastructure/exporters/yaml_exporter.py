"""YamlStoryExporter — vuelca un Story al formato YAML canónico (Spec-217).

El YAML producido es input válido del comando `generate --input` (round-trip
bidireccional) y refleja 1:1 la estructura interna de `storyteller_config`
que lee la ficha de la historia.

Spec-190 §T6.2: el `narrator_config` persistido ya no contiene `atmosphere`,
`scenarios`, `rules` ni `actos` (ni `entities`, Spec-450). El exporter los
reconstruye dentro del bloque `storyteller_config` del YAML desde las
columnas/tablas correspondientes.
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
        sc = story.narrator_config or {}
        personajes = self._build_personajes(story)

        doc = {
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
        # Spec-530: solo si la historia pasó por el asistente (los YAML viejos no cambian).
        if story.direction:
            doc["direction"] = story.direction.model_dump(mode="json")
        if story.workshop:
            doc["workshop"] = [w.model_dump(mode="json") for w in story.workshop]
        if story.outline:
            doc["outline"] = [a.model_dump(mode="json") for a in story.outline]
        return doc

    def _build_personajes(self, story: Story) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for idx, p in enumerate(story.personajes_full or [], start=1):
            out.append(
                {
                    "id": p.get("id") or f"P{idx}",
                    "name": p.get("name", ""),
                    "role": p.get("role", ""),
                }
            )
            # Spec-530: tipo y relación con quien narra, solo si no son los de siempre.
            if p.get("kind") and p["kind"] != "persona":
                out[-1]["kind"] = p["kind"]
            if p.get("relation"):
                out[-1]["relation"] = p["relation"]
        return out

    def _derive_escenarios_str(self, sc: dict, story: Story) -> str:
        if story.scenarios:
            parts = []
            for s in story.scenarios:
                parts.append(f"{s.name}: {s.description}" if s.description else s.name)
            return "; ".join(parts)
        return ""

    def authoring_config(self, story: Story) -> dict[str, Any]:
        """`storyteller_config` completo (mismo que el YAML) para la ficha de la historia."""
        return self._build_storyteller_config(story.narrator_config or {}, story)

    def _build_storyteller_config(self, sc: dict, story: Story) -> dict[str, Any]:
        """Reconstruye el bloque canónico, completando lo que falte desde Story."""
        scenarios = self._build_scenarios(sc, story)
        rules = self._build_rules(sc, story)
        actos = self._build_actos(sc, story)

        return {
            "storyteller_id": sc.get("storyteller_id") or "P1",
            "storyteller_name": sc.get("storyteller_name") or "",
            "voice": {
                "person": sc.get("voice", {}).get("person", "primera"),
                "tense": sc.get("voice", {}).get("tense", "pasado"),
            },
            "atmosphere": {"genre": story.genero, "subgenre": story.subgenero},
            "scenarios": scenarios,
            "rules": rules,
            "entities": self._build_entities(story),
            "actos": actos,
        }

    def _build_scenarios(self, sc: dict, story: Story) -> list[dict[str, Any]]:
        # Spec-190 §T6.2: los escenarios viven en la tabla `scenario` (con
        # description), ya no dentro del JSON narrator_config.
        return [
            {"id": f"S{i}", "order": i, "name": s.name, "description": s.description or ""}
            for i, s in enumerate(story.scenarios or [], start=1)
        ]

    def _build_entities(self, story: Story) -> list[dict[str, Any]]:
        # Spec-450: viven en la tabla `entity`; la primera es la principal.
        return [
            {
                "name": e.name,
                "nature": e.nature_id,
                "description": e.description,
                "manifestations": e.manifestations,
                "limits": e.limits,
                "reveal_level": e.reveal_level.value,
            }
            for e in story.entities
        ]

    def _build_rules(self, sc: dict, story: Story) -> list[dict[str, Any]]:
        if story.typed_rules:
            out = []
            for idx, r in enumerate(story.typed_rules, start=1):
                out.append({"id": r.id or f"R{idx}", "text": r.content})
                if r.applies_to_beat:
                    out[-1]["applies_to_beat"] = r.applies_to_beat
            return out
        rich = sc.get("rules") or []  # historias viejas: el JSON aún las traía
        if rich:
            return [
                {"id": r.get("id") or f"R{i}", "text": r.get("text") or r.get("content", "")}
                for i, r in enumerate(rich, start=1)
            ]
        return [{"id": f"R{i}", "text": txt} for i, txt in enumerate(story.reglas or [], start=1)]

    def _build_actos(self, sc: dict, story: Story) -> dict[str, dict[str, Any]]:
        """Texto de cada acto, de la fuente más fiel disponible (Spec-440 §8).

        1. `narrator_config.actos` (historias viejas: el JSON aún los traía);
        2. `macro_beat.synopsis_beat` (donde los guarda CreateStoryUseCase);
        3. `sinopsis` partida en 5 párrafos (el wizard la arma uniendo los actos
           con una línea en blanco; tras una generación web es la única copia).
        """
        actos_raw = sc.get("actos") or {}
        by_beat = {b.number: (b.synopsis_beat or "") for b in (story.beats or [])}
        paragraphs = [p.strip() for p in (story.sinopsis or "").split("\n\n") if p.strip()]
        from_sinopsis = paragraphs if len(paragraphs) == 5 else []
        canonical_keys = [
            ("act_1", "exposicion"),
            ("act_2", "accion_ascendente"),
            ("act_3", "climax"),
            ("act_4", "accion_descendente"),
            ("act_5", "desenlace"),
        ]
        out: dict[str, dict[str, Any]] = {}
        for number, (key, default_type) in enumerate(canonical_keys, start=1):
            block = actos_raw.get(key) or {}
            text = block.get("text", "") if isinstance(block, dict) else str(block)
            if not text:
                text = by_beat.get(number, "")
            if not text and from_sinopsis:
                text = from_sinopsis[number - 1]
            out[key] = {
                "type": (block.get("type") if isinstance(block, dict) else None) or default_type,
                "text": _LiteralStr(text) if text else "",
            }
        return out
