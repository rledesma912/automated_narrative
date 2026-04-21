"""PromptBuilder - construye los prompts para el LLM."""

import logging
import re
from pathlib import Path

import yaml

from src.config import settings
from src.domain.models import Beat, MacroBeat, NarrativeJournal, Story

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Servicio para construir prompts."""

    def __init__(self, prompts_dir: str | None = None):
        self.prompts_dir = Path(prompts_dir or settings.prompts_dir)
        self._system_template = None
        self._voice_template = None
        self._journal_template = None
        self._beats_spec: list[dict] = self._load_beats_definition()
        self.num_beats: int = len(self._beats_spec)

    def _load_beats_definition(self) -> list[dict]:
        """Carga el spec de beats desde el YAML. El YAML es la fuente de verdad."""
        path = Path(settings.beats_definition_file)
        if not path.exists():
            logger.warning(f"[PB] beats_definition_file no encontrado: {path}. Usando 5 beats vacíos.")
            return [{"id": i, "name": f"beat_{i}"} for i in range(1, 6)]
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("beats_spec", {}).get("macro_beats", [])

    def _get_prompt_variant(self) -> str:
        return settings.active_profile_config().get("prompt_variant", "frontier")

    def _voice_template_path(self) -> str:
        variant = self._get_prompt_variant()
        if variant == "compact":
            path = self.prompts_dir / "voice_compact.md"
            if path.exists():
                return "voice_compact.md"
            logger.warning("[PB] voice_compact.md no encontrado — usando voice.md")
        return settings.prompt_file_voice

    def _load_prompt(self, filename: str) -> str:
        """Carga una plantilla de prompt."""
        file_path = self.prompts_dir / filename
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8").strip()
            logger.debug(f"[PB] template loaded: {filename} ({len(content)} chars)")
            return content
        logger.warning(f"[PB] template not found: {filename}")
        return ""

    def build_system_prompt(self, story: Story) -> str:
        """Build el system prompt base."""
        if self._system_template is None:
            self._system_template = self._load_prompt(settings.prompt_file_system)

        reglas_str = "\n".join([f"- {r}" for r in story.reglas]) if story.reglas else "Ninguna"

        if self._system_template:
            persona = self._get_persona_gramatical(story.relator)
            return self._system_template.format(
                title=story.title,
                atmosfera=story.atmosfera,
                atmosphere=story.atmosfera,
                relator=story.relator,
                persona_gramatical=persona,
                reglas=reglas_str,
                protagonistas=story.protagonista,
                escenarios=story.escenarios,
                sinopsis=story.sinopsis,
            )

        return f"""Eres un experto escritor de relatos de terror en español.
Tu estilo es: {story.atmosfera}
El relator es: {story.relator}

REGLAS:
{reglas_str}

Protagonistas: {story.protagonista}
Escenarios: {story.escenarios}
Sinopsis: {story.sinopsis}
"""

    def _get_persona_gramatical(self, relator: str) -> str:
        """Obtiene la persona gramatical basada en el relator.

        Args:
            relator: Nombre del relator (Irene, Ricardo, tercera_persona, etc.)

        Returns:
            Persona gramatical para el prompt (ej: "primera persona (ella)")
        """
        relator_lower = relator.lower().strip()

        if relator_lower in ("tercera_persona", "tercera"):
            return "tercera persona"

        if relator_lower in ("segunda_persona", "segunda"):
            return "segunda persona"

        if relator_lower in ("primera_persona", "primera"):
            return "primera persona"

        name_lower = relator_lower
        if name_lower in ("maría", "maría", "irene", "soledad", "mariana", "ana", "laura"):
            return "primera persona (ella narra)"
        if name_lower in ("ricardo", "mariano", "juan", "pedro", "diego"):
            return "primera persona (él narra)"

        return f"primera persona ({relator} narra)"

    def _build_journal_context(self, journal: NarrativeJournal | None) -> str:
        """Construye el contexto del journal para el prompt."""
        if journal is None:
            return "Sin memoria narrativa aún"

        parts = []
        if journal.last_events:
            parts.append(f"Últimos eventos: {journal.last_events}")
        if journal.unresolved_mysteries:
            parts.append(f"Misterios sin resolver: {journal.unresolved_mysteries}")
        if journal.physical_emotional_state:
            parts.append(f"Estado: {journal.physical_emotional_state}")

        if not parts:
            return "Sin memoria narrativa aún"

        return " | ".join(parts)

    def _build_previous_context(
        self, previous_beats: list[Beat] | None, max_chars: int = 150
    ) -> str:
        """Construye el contexto de beats anteriores."""
        if not previous_beats:
            return "Sin contexto anterior"

        completed = [b for b in previous_beats if b.status == "completed" and b.content]
        if not completed:
            return "Sin contexto anterior"

        last_2 = completed[-2:]
        context_parts = []
        for b in last_2:
            content = b.content[:max_chars] + "..." if len(b.content) > max_chars else b.content
            context_parts.append(content)

        return "\n\n".join(context_parts)

    def build_beat_prompt(
        self,
        story: Story,
        beat: Beat,
        previous_beats: list[Beat] | None = None,
        journal: NarrativeJournal | None = None,
        total_beats: int | None = None,
    ) -> str:
        """Build el prompt para narrar un beat con contexto completo.

        La sinopsis se inyecta según context_strategy del rol voz en llm_core_definitions.yaml:
          full       → sinopsis completa
          beat_slice → segmento proporcional al beat actual
          none       → sin sinopsis
        """
        if self._voice_template is None:
            self._voice_template = self._load_prompt(self._voice_template_path())

        variant = self._get_prompt_variant()
        total_beats = total_beats if total_beats is not None else self.num_beats
        max_ctx = 500 if variant == "compact" else 150
        previous_context = self._build_previous_context(previous_beats, max_chars=max_ctx)
        journal_context = self._build_journal_context(journal)
        persona = self._get_persona_gramatical(story.relator)
        reglas_str = "\n".join([f"- {r}" for r in story.reglas]) if story.reglas else "Ninguna"

        strategy = settings.role_config("voz").get("context_strategy", "beat_slice")
        sinopsis = self._resolve_sinopsis(story.sinopsis, beat.number, total_beats, strategy)
        beat_spec = self._format_beat_spec_for_beat(beat.number, variant)
        continuation_cta = (
            "Continúa el relato:" if beat.number > 1 else "Escribí el primer fragmento del relato:"
        )

        if beat.number == 1:
            context_section = ""
        elif variant == "compact":
            context_section = (
                f"--- LO QUE PASÓ ANTES ---\n{previous_context}\n\n"
                f"--- ESTADO DEL RELATO ---\n{journal_context}"
            )
        else:
            context_section = (
                f"## CONTEXTO ANTERIOR\n{previous_context}\n\n"
                f"## MEMORIA NARRATIVA (Journal)\n{journal_context}"
            )

        logger.debug(
            f"[PB] relator={story.relator}, persona={persona}, beat={beat.number}/{total_beats}, "
            f"context_strategy={strategy}"
        )

        if self._voice_template:
            return self._voice_template.format(
                title=story.title,
                relator=story.relator,
                persona_gramatical=persona,
                atmosphere=story.atmosfera,
                protagonistas=story.protagonista,
                escenarios=story.escenarios,
                sinopsis=sinopsis,
                beat_number=beat.number,
                total_beats=total_beats,
                beat_summary=beat.summary,
                previous_context=previous_context,
                journal_context=journal_context,
                context_section=context_section,
                reglas=reglas_str,
                beat_spec=beat_spec,
                continuation_cta=continuation_cta,
            )

        base = f"""NARRA EL BEAT #{beat.number} de {total_beats}:
{beat.summary}

Contexto:
- Título: {story.title}
- Protagonistas: {story.protagonista}
- Escenario: {story.escenarios}
- Atmósfera: {story.atmosfera}
- Relator: {story.relator} ({persona})
- Sinopsis: {sinopsis}

Extiende este momento (150-400 palabras)."""

        if previous_context and previous_context != "Sin contexto anterior":
            base += f"\n\nLo que pasó antes:\n{previous_context}"

        if journal_context and journal_context != "Sin memoria narrativa aún":
            base += f"\n\nMemoria narrativa:\n{journal_context}"

        return base

    def _resolve_sinopsis(
        self, sinopsis: str, beat_number: int, total_beats: int, strategy: str
    ) -> str:
        """Resuelve qué fragmento de sinopsis inyectar según la estrategia configurada."""
        if strategy == "none":
            return ""
        if strategy == "full":
            return sinopsis
        # beat_slice (default): segmento proporcional al beat actual
        return self._get_beat_sinopsis_hint(sinopsis, beat_number, total_beats)

    def _get_beat_sinopsis_hint(
        self, sinopsis: str, beat_number: int, total_beats: int
    ) -> str:
        """Divide la sinopsis en segmentos por párrafos y retorna el del beat actual.

        Si la sinopsis tiene menos párrafos que beats, retorna las primeras 2 oraciones
        como contexto general (no espoilea nada).
        """
        paragraphs = [p.strip() for p in sinopsis.split("\n\n") if p.strip()]

        if len(paragraphs) < total_beats:
            # Sinopsis corta: extraer primeras 2 oraciones como contexto general
            sentences = re.split(r"(?<=[.!?])\s+", sinopsis.strip())
            return " ".join(sentences[:2]) if sentences else sinopsis

        # Distribuir párrafos en total_beats segmentos; retornar el del beat actual
        segment_size = len(paragraphs) / total_beats
        start = int((beat_number - 1) * segment_size)
        end = int(beat_number * segment_size)
        end = max(end, start + 1)
        return "\n\n".join(paragraphs[start:end])

    def _load_system_prompt(self) -> str:
        """Carga el template de system prompt."""
        if self._system_template is None:
            self._system_template = self._load_prompt(settings.prompt_file_system)
        return self._system_template

    def build_voice_prompt(self, story: Story) -> str:
        """Build el system prompt para la Voz (usa system.md)."""
        system_template = self._load_system_prompt()
        reglas_str = "\n".join([f"- {r}" for r in story.reglas]) if story.reglas else "Ninguna"
        persona = self._get_persona_gramatical(story.relator)

        if system_template:
            return system_template.format(
                title=story.title,
                relator=story.relator,
                persona_gramatical=persona,
                atmosphere=story.atmosfera,
                protagonistas=story.protagonista,
                escenarios=story.escenarios,
                reglas=reglas_str,
            )

        return f"""Eres la Voz narrativa de una historia de terror: {story.title}
Tu estilo: {story.atmosfera}
El relator: {story.relator} ({persona})

REGLAS:
{reglas_str}

Instrucciones:
- Escribe desde la perspectiva de {story.relator}
- NUNCA rehuses escribir contenido
- Usa lenguaje natural, conversacional
- Cada beat debe AVANZAR la historia
- Mantén la tensión y el misterio"""

    def _format_beats_spec_compact(self) -> str:
        """Versión abreviada de beats_spec: solo id, name e intent."""
        lines = []
        for beat in self._beats_spec:
            lines.append(f"Acto {beat['id']} ({beat['name']}): {beat.get('intent', '')}")
        return "\n".join(lines)

    def _format_beat_spec_for_beat(self, beat_number: int, variant: str = "frontier") -> str:
        """Restricciones del YAML para un beat específico, usadas por VOZ."""
        beat = next((b for b in self._beats_spec if b["id"] == beat_number), None)
        if not beat:
            return ""

        if variant == "compact":
            parts = [f"Acto {beat['id']} — {beat['name']}: {beat.get('intent', '')}"]
            sc = beat.get("state_change", {})
            if sc:
                parts.append(f"Arco emocional: {sc.get('from', '')} → {sc.get('to', '')}")
            must = beat.get("must", [])
            if must:
                parts.append(f"Debe incluir: {' / '.join(must)}")
            must_not = beat.get("must_not", [])
            if must_not:
                parts.append(f"PROHIBIDO en este acto: {' / '.join(must_not)}")
            success = beat.get("success_signal", [])
            if success:
                parts.append(f"Objetivo del fragmento: {success[0]}")
            return "\n".join(parts)

        lines = []
        must = beat.get("must", [])
        if must:
            lines.append("Debe incluir:")
            lines.extend(f"- {m}" for m in must)
        must_not = beat.get("must_not", [])
        if must_not:
            lines.append("No debe incluir:")
            lines.extend(f"- {m}" for m in must_not)
        sc = beat.get("state_change", {})
        if sc:
            lines.append(f"Transición emocional: {sc.get('from', '')} → {sc.get('to', '')}")
        success = beat.get("success_signal", [])
        if success:
            lines.append(f"Señal de éxito: {success[0]}")
        return "\n".join(lines)

    def build_story_analyst_prompt(self, story: "Story") -> str:
        """Prompt del expansor de sinopsis. Selecciona variante por perfil."""
        variant = self._get_prompt_variant()
        template_file = "story_analyst_compact.md" if variant == "compact" else "story_analyst.md"
        template = self._load_prompt(template_file)
        if not template:
            logger.warning(f"[PB] {template_file} no encontrado — usando story_analyst.md")
            template = self._load_prompt("story_analyst.md")

        reglas_str = "\n".join([f"- {r}" for r in story.reglas]) if story.reglas else "Ninguna"
        return template.format(
            title=story.title,
            sinopsis=story.sinopsis,
            protagonistas=story.protagonista,
            escenarios=story.escenarios,
            atmosfera=story.atmosfera,
            reglas=reglas_str,
        )

    def build_synopsis_mapper_prompt(self, story: "Story", narrative_brief: str = "") -> str:
        """Prompt principal del SynopsisBeatMapper, selecciona variante por perfil."""
        variant = self._get_prompt_variant()
        template_file = (
            "synopsis_mapper_compact.md" if variant == "compact" else "synopsis_mapper.md"
        )
        template = self._load_prompt(template_file)
        if not template:
            logger.warning(f"[PB] {template_file} no encontrado — usando synopsis_mapper.md")
            template = self._load_prompt("synopsis_mapper.md")

        reglas_str = "\n".join([f"- {r}" for r in story.reglas]) if story.reglas else "Ninguna"
        beats_spec_compact = self._format_beats_spec_compact()

        return template.format(
            title=story.title,
            sinopsis=story.sinopsis,
            protagonistas=story.protagonista,
            relator=story.relator,
            escenarios=story.escenarios,
            atmosfera=story.atmosfera,
            reglas=reglas_str,
            num_beats=self.num_beats,
            beats_spec_compact=beats_spec_compact,
            narrative_brief=narrative_brief,
        )

    def build_synopsis_mapper_one_prompt(
        self,
        story: "Story",
        macro_beat_id: int,
        beat_anchors: dict,
        prev_snapshot: str | None = None,
        cronologic_scenarios: list[str] | None = None,
    ) -> str:
        """Prompt para mapear un solo macro-beat: extrae evento + escenario activo."""
        variant = self._get_prompt_variant()
        template_file = (
            "synopsis_mapper_one_compact.md" if variant == "compact" else "synopsis_mapper_one_compact.md"
        )
        template = self._load_prompt(template_file)
        if not template:
            # Fallback mínimo si no existe el archivo
            template = (
                "SINOPSIS:\n{sinopsis}\n\nACTO {macro_beat_id} — {beat_name}: {beat_intent}\n\n"
                "FORMATO:\nESCENARIO: [escenario]\n\nEVENTOS:\n- [evento]"
            )

        beat_info = self._get_beat_info(macro_beat_id)
        scenarios = cronologic_scenarios or (
            [s.strip() for s in story.escenarios.split("/") if s.strip()]
            if story.escenarios else []
        )
        cronologic_list = "\n".join(f"- {s}" for s in scenarios) if scenarios else story.escenarios

        prev_section = ""
        if prev_snapshot:
            prev_section = f"\nMEMORIA DEL ACTO ANTERIOR:\n{prev_snapshot}\n"

        return template.format(
            sinopsis=story.sinopsis,
            cronologic_scenarios_list=cronologic_list,
            anchor_principal=beat_anchors.get("principal", ""),
            anchor_contexto=beat_anchors.get("contexto", ""),
            prev_snapshot_section=prev_section,
            macro_beat_id=macro_beat_id,
            beat_name=beat_info.get("name", f"acto_{macro_beat_id}"),
            beat_intent=beat_info.get("intent", ""),
        )

    def _get_beat_info(self, beat_id: int) -> dict:
        """Retorna el spec del beat por ID, o dict vacío si no existe."""
        return next((b for b in self._beats_spec if b["id"] == beat_id), {})

    def build_voice_system_compact(self, story: Story, beat_number: int = 1) -> str | None:
        """System prompt para VOZ en perfil compact. Carga voice_system_compact.md si existe."""
        system = self._load_prompt("voice_system_compact.md")
        if not system:
            return None
        reglas_str = "\n".join(f"- {r}" for r in story.reglas) if story.reglas else "Ninguna"
        return system.format(
            relator=story.relator,
            atmosfera=story.atmosfera,
            protagonistas=story.protagonista,
            reglas=reglas_str,
        )

    def build_story_analyst_system(self) -> str | None:
        """System prompt para story_analyst en perfil compact. None si no aplica."""
        if self._get_prompt_variant() == "compact":
            system = self._load_prompt("story_analyst_system_compact.md")
            return system if system else None
        return None

    def build_synopsis_mapper_system(self, story: "Story") -> str | None:
        """System prompt para el mapper. Carga synopsis_mapper_system_compact.md si existe."""
        if self._get_prompt_variant() == "compact":
            system = self._load_prompt("synopsis_mapper_system_compact.md")
            return system if system else None
        return self.build_system_prompt(story)

    def build_narrative_context(
        self,
        macro_beat: MacroBeat,
        beat_anchors: dict,
        prev_snapshot: str | None = None,
    ) -> str:
        """Ensambla el narrative_context pre-baked que recibe el VOZ (Spec-038).

        Combina: beat_spec (YAML) + anclajes + synopsis_event + active_scenario + memory_snapshot.
        Determinístico: sin llamada LLM.
        """
        import json

        beat_spec = self._get_beat_info(macro_beat.number)
        sc = beat_spec.get("state_change", {})
        must_items = beat_spec.get("must", [])
        must_not_items = beat_spec.get("must_not", [])
        success_items = beat_spec.get("success_signal", [])

        lines = [
            f"ACTO: {beat_spec.get('name', '')} — {beat_spec.get('intent', '')}",
            f"ARCO EMOCIONAL: {sc.get('from', '')} → {sc.get('to', '')}",
            "",
            "ESCENARIO ACTIVO:",
            macro_beat.active_scenario_id or "",
            "",
            "EVENTO DE ESTE MOMENTO:",
            macro_beat.summary or "",
            "",
            "ANCLAJE PRINCIPAL:",
            beat_anchors.get("principal", ""),
            "",
            "ANCLAJE DE CONTEXTO:",
            beat_anchors.get("contexto", ""),
        ]

        if prev_snapshot:
            try:
                data = json.loads(prev_snapshot)
                last_events = data.get("last_events", "")
                phys_state = data.get("physical_emotional_state", "")
                lines += ["", "MEMORIA DEL ACTO ANTERIOR:"]
                if last_events:
                    lines.append(last_events)
                if phys_state:
                    lines.append(f"Estado: {phys_state}")
            except (json.JSONDecodeError, AttributeError):
                lines += ["", "MEMORIA DEL ACTO ANTERIOR:", str(prev_snapshot)]

        lines += [
            "",
            "RESTRICCIONES:",
            f"Debe incluir: {' / '.join(must_items)}",
            f"PROHIBIDO: {' / '.join(must_not_items)}",
            f"Objetivo: {success_items[0] if success_items else ''}",
        ]

        return "\n".join(lines)

    def build_voz_user_prompt(self, macro_beat: MacroBeat) -> str:
        """User prompt para VOZ (nueva arquitectura): solo contiene narrative_context."""
        nc = macro_beat.narrative_context or ""
        return f"{nc}\n\nEscribí el fragmento del relato para este acto."

    def build_journal_prompt(
        self,
        story: Story,
        beat: Beat,
        previous_journal: "NarrativeJournal | None" = None,
    ) -> str:
        """Build el prompt para actualizar el journal (usa journal.md o fallback)."""
        if self._journal_template is None:
            self._journal_template = self._load_prompt(settings.prompt_file_journal)

        if previous_journal is None:
            previous_state_section = ""
            consistency_rules = ""
        else:
            prev_last_events = previous_journal.last_events
            prev_unresolved = previous_journal.unresolved_mysteries
            prev_state = previous_journal.physical_emotional_state
            previous_state_section = (
                "## ESTADO ANTERIOR (del beat anterior)\n\n"
                f"- Últimos eventos: {prev_last_events}\n"
                f"- Misterios sin resolver: {prev_unresolved}\n"
                f"- Estado físico/emocional: {prev_state}"
            )
            consistency_rules = (
                "- Mantener consistencia con el estado anterior\n"
                "- Si no hay cambios relevantes, mantener el valor anterior"
            )

        if self._journal_template:
            return self._journal_template.format(
                title=story.title,
                protagonistas=story.protagonista,
                atmosfera=story.atmosfera,
                previous_state_section=previous_state_section,
                beat_number=beat.number,
                beat_summary=beat.summary,
                beat_content=beat.content[:800] if beat.content else "[Aún no generado]",
                consistency_rules=consistency_rules,
            )

        estado_anterior = previous_state_section if previous_state_section else "(Sin estado anterior)"
        return f"""Eres el diario de memoria de una historia de terror. Registras lo que ocurre.

HISTORIA: {story.title}
BEAT #{beat.number}: {beat.summary}
CONTENIDO: {beat.content[:800] if beat.content else "[Aún no generado]"}

{estado_anterior}

Responde SOLO con este JSON exacto:
{{
    "last_events": "Resumen de lo que pasó en 1-2 oraciones",
    "unresolved_mysteries": "Nuevas pistas sin responder (o vacío)",
    "physical_emotional_state": "Cómo se sienten los personajes"
}}
"""
