"""PromptBuilder - construye los prompts para el LLM."""

import logging
from pathlib import Path

from src.application.services.beat_spec_repository import BeatSpecRepository
from src.application.services.narrative_context_assembler import NarrativeContextAssembler
from src.application.services.persona_service import PersonaService
from src.application.services.prompt_strategies import (
    CompactStrategy,
    FrontierStrategy,
    IPromptStrategy,
)
from src.application.services.synopsis_slice_resolver import SynopsisSliceResolver
from src.application.services.template_loader import TemplateLoader
from src.config import settings
from src.domain.models import Beat, MacroBeat, NarrativeJournal, Story

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Facade delgada: delega a componentes internos, expone la misma API pública."""

    def __init__(self, prompts_dir: str | None = None):
        self.prompts_dir = Path(prompts_dir or settings.prompts_dir)
        self._loader = TemplateLoader(self.prompts_dir)
        self._beat_repo = BeatSpecRepository()
        self._persona = PersonaService()
        self._synopsis = SynopsisSliceResolver()
        self._nc_assembler = NarrativeContextAssembler(self._beat_repo)
        self._beats_spec: list[dict] = self._beat_repo.get_all()
        self.num_beats: int = self._beat_repo.num_beats
        self._strategy: IPromptStrategy | None = None

    def get_variant_name(self) -> str:
        """Retorna el nombre de la variante activa (compact, frontier, etc)."""
        return self._get_strategy().variant_name

    def _get_strategy(self) -> IPromptStrategy:
        if self._strategy:
            return self._strategy
        variant = self._loader.get_variant()
        if variant == "compact":
            self._strategy = CompactStrategy()
        else:
            self._strategy = FrontierStrategy()
        return self._strategy

    def _load_prompt(self, filename: str) -> str:
        return self._loader.load(filename)

    def build_system_prompt(self, story: Story) -> str:
        """Build el system prompt base."""
        # El system prompt suele ser fijo (system.md), pero usamos la estrategia para el nombre si fuera necesario
        strategy = self._get_strategy()
        template_name = strategy.get_template_name("system").replace("_compact.md", ".md") # system.md es compartido usualmente
        template = self._load_prompt(template_name)
        reglas_str = "\n".join([f"- {r}" for r in story.reglas]) if story.reglas else "Ninguna"
        escenarios_str = (
            "\n".join([f"- {s.name}" for s in story.scenarios]) if story.scenarios else "No definidos"
        )

        if template:
            persona = self._get_persona_gramatical(story.relator, config=story.storyteller_config)
            return template.format(
                title=story.title,
                atmosfera=story.atmosfera,
                atmosphere=story.atmosfera,
                relator=story.relator,
                persona_gramatical=persona,
                reglas=reglas_str,
                protagonistas=story.protagonista,
                escenarios=escenarios_str,
                sinopsis=story.sinopsis,
            )

        return f"""Eres un experto escritor de relatos de terror en español.
Tu estilo es: {story.atmosfera}
El relator es: {story.relator}

REGLAS:
{reglas_str}

Protagonistas: {story.protagonista}
Escenarios: {story.scenarios}
Sinopsis: {story.sinopsis}
"""

    def _get_persona_gramatical(self, relator: str, config: dict | None = None) -> str:
        return self._persona.resolve(relator, storyteller_config=config)

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
        """Build el prompt para narrar un beat con contexto completo."""
        strategy = self._get_strategy()
        voice_template = self._load_prompt(strategy.get_template_name("voice"))
        total_beats = total_beats if total_beats is not None else self.num_beats

        previous_context = self._build_previous_context(previous_beats, max_chars=strategy.max_context_chars)
        journal_context = self._build_journal_context(journal)
        persona = self._get_persona_gramatical(story.relator, config=story.storyteller_config)
        reglas_str = "\n".join([f"- {r}" for r in story.reglas]) if story.reglas else "Ninguna"
        escenarios_str = (
            "\n".join([f"- {s.name}" for s in story.scenarios]) if story.scenarios else "No definidos"
        )

        sinopsis = self._resolve_sinopsis(story.sinopsis, beat.number, total_beats, "beat_slice")
        beat_spec = self._format_beat_spec_for_beat(beat.number, strategy.variant_name)

        # Enriquecimiento con metadatos del YAML (Slice 3)
        beat_def = self._beat_repo.get_by_id(beat.number)
        intensity = beat_def.get("intensity", "media")
        success_signal = beat_def.get("success_signal", ["No definida"])[0]
        state_change = beat_def.get("state_change", {})

        meta_context = strategy.format_beat_metadata(intensity, success_signal, state_change)
        context_section = strategy.format_context_section(previous_context, journal_context, beat.number)

        continuation_cta = (
            "Continúa el relato:" if beat.number > 1 else "Escribí el primer fragmento del relato:"
        )

        logger.debug(
            f"[PB] relator={story.relator}, persona={persona}, beat={beat.number}/{total_beats}"
        )

        word_limit = self._beat_repo.get_word_limit(beat.number, "entre 350 y 430 palabras")

        if voice_template:
            # Añadimos meta_context si el template tiene el placeholder o lo inyectamos en beat_spec
            full_beat_spec = f"{beat_spec}\n\n--- GUÍA DE TONO ---\n{meta_context}"

            return voice_template.format(
                title=story.title,
                relator=story.relator,
                persona_gramatical=persona,
                atmosphere=story.atmosfera,
                protagonistas=story.protagonista,
                escenarios=escenarios_str,
                sinopsis=sinopsis,
                beat_number=beat.number,
                total_beats=total_beats,
                beat_summary=beat.summary,
                previous_context=previous_context,
                journal_context=journal_context,
                context_section=context_section,
                reglas=reglas_str,
                beat_spec=full_beat_spec,
                continuation_cta=continuation_cta,
                word_limit=word_limit,
            )

        base = f"""NARRA EL BEAT #{beat.number} de {total_beats}:
{beat.summary}

Contexto:
- Título: {story.title}
- Protagonistas: {story.protagonista}
- Escenario: {escenarios_str}
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
        return self._synopsis.resolve(sinopsis, beat_number, total_beats, strategy)

    def get_beat_sinopsis_slice(
        self, sinopsis: str, beat_number: int, total_beats: int
    ) -> str:
        return self._synopsis.get_slice(sinopsis, beat_number, total_beats)

    def build_voice_prompt(self, story: Story) -> str:
        """Build el system prompt para la Voz (usa system.md)."""
        system_template = self._load_prompt(settings.prompt_file_system)
        reglas_str = "\n".join([f"- {r}" for r in story.reglas]) if story.reglas else "Ninguna"
        escenarios_str = (
            "\n".join([f"- {s.name}" for s in story.scenarios]) if story.scenarios else "No definidos"
        )
        persona = self._get_persona_gramatical(story.relator)

        if system_template:
            return system_template.format(
                title=story.title,
                relator=story.relator,
                persona_gramatical=persona,
                atmosphere=story.atmosfera,
                protagonistas=story.protagonista,
                escenarios=escenarios_str,
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
        return self._beat_repo.format_compact()

    def _format_beat_spec_for_beat(self, beat_number: int, variant: str = "frontier") -> str:
        return self._beat_repo.format_for_beat(beat_number, variant)

    def build_story_analyst_prompt(self, story: "Story") -> str:
        """Prompt del expansor de sinopsis. Selecciona variante por perfil."""
        strategy = self._get_strategy()
        template_file = strategy.get_template_name("story_analyst")
        template = self._load_prompt(template_file)
        if not template:
            logger.warning(f"[PB] {template_file} no encontrado — usando story_analyst.md")
            template = self._load_prompt("story_analyst.md")

        reglas_str = "\n".join([f"- {r}" for r in story.reglas]) if story.reglas else "Ninguna"
        return template.format(
            title=story.title,
            sinopsis=story.sinopsis,
            protagonistas=story.protagonista,
            escenarios=[s.name for s in story.scenarios] if story.scenarios else [],
            atmosfera=story.atmosfera,
            reglas=reglas_str,
        )

    def build_synopsis_mapper_prompt(self, story: "Story", narrative_brief: str = "") -> str:
        """Prompt principal del SynopsisBeatMapper, selecciona variante por perfil."""
        strategy = self._get_strategy()
        template_file = strategy.get_template_name("synopsis_mapper")
        template = self._load_prompt(template_file)
        if not template:
            logger.warning(f"[PB] {template_file} no encontrado — usando synopsis_mapper.md")
            template = self._load_prompt("synopsis_mapper.md")

        reglas_str = "\n".join([f"- {r}" for r in story.reglas]) if story.reglas else "Ninguna"
        escenarios_str = (
            "\n".join([f"- {s.name}" for s in story.scenarios]) if story.scenarios else "No definidos"
        )
        beats_spec_compact = self._format_beats_spec_compact()

        return template.format(
            title=story.title,
            sinopsis=story.sinopsis,
            protagonistas=story.protagonista,
            relator=story.relator,
            escenarios=escenarios_str,
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
        synopsis_slice: str | None = None,
        active_rules: list[str] | None = None,
        active_scenario: str | None = None,
        beat_intent: str | None = None,
        beat_type: str | None = None,
        beat_intensity: str | None = None,
        atmosphere: str | None = None,
    ) -> str:
        """Prompt para mapear un solo macro-beat: extrae evento + escenario activo."""
        strategy = self._get_strategy()
        template_file = strategy.get_template_name("synopsis_mapper_one")
        template = self._load_prompt(template_file)
        if not template:
            # Fallback mínimo si no existe el archivo
            template = (
                "SINOPSIS (FRAGMENTO):\n{synopsis_slice}\n\n"
                "ATMÓSFERA: {atmosphere}\n"
                "INTENTO NARRATIVO: {beat_intent}\n"
                "ESCENARIO: {active_scenario}\n"
                "REGLAS: {active_rules}\n\n"
                "ACTO {macro_beat_id} — {beat_name}\n\n"
                "FORMATO:\nESCENARIO: [nombre]\n\nEVENTOS:\n- [evento]"
            )

        beat_info = self.get_beat_info(macro_beat_id)

        synopsis_slice_val = synopsis_slice or story.sinopsis
        active_rules_str = "\n".join(f"- {r}" for r in active_rules) if active_rules else "Ninguna"
        active_scenario_val = active_scenario or "No especificado"
        beat_intent_val = beat_intent or beat_info.get("intent", "")
        beat_type_val = beat_type or beat_info.get("name", "")
        beat_intensity_val = beat_intensity or beat_info.get("intensity", "")
        atmosphere_val = atmosphere or story.atmosfera

        prev_section = ""
        if prev_snapshot:
            prev_section = f"\nMEMORIA DEL ACTO ANTERIOR:\n{prev_snapshot}\n"

        return template.format(
            sinopsis=story.sinopsis,
            synopsis_slice=synopsis_slice_val,
            active_rules=active_rules_str,
            active_scenario=active_scenario_val,
            beat_intent=beat_intent_val,
            beat_type=beat_type_val,
            beat_intensity=beat_intensity_val,
            atmosphere=atmosphere_val,
            anchor_principal=beat_anchors.get("resonance", ""),
            anchor_contexto="",
            prev_snapshot_section=prev_section,
            macro_beat_id=macro_beat_id,
            beat_name=beat_info.get("name", f"acto_{macro_beat_id}"),
            beat_intent_legacy=beat_info.get("intent", ""),
        )

    def get_beat_info(self, beat_id: int) -> dict:
        return self._beat_repo.get_by_id(beat_id)

    def _build_storyteller_block(self, config: dict) -> str:
        """Formatea storyteller_config completo para el prompt (Spec-070/180)."""
        if not config:
            return ""
        lines = ["== Perfil del Narrador =="]

        # Percepción
        perception = config.get("perception", {})
        if perception:
            reliability = perception.get("reliability", "")
            distortion = perception.get("distortion", {})
            dist_level = distortion.get("level", "") if isinstance(distortion, dict) else ""
            line = f"Percepción: {reliability}"
            if dist_level:
                line += f" (Distorsión: {dist_level})"
            lines.append(line)

        # Voz y Lenguaje
        voice = config.get("voice", {})
        lang = config.get("language", {})
        v_parts = [voice.get("person", ""), voice.get("tense", ""), voice.get("style", "")]
        v_parts = [p for p in v_parts if p]
        l_parts = [lang.get("register", ""), lang.get("figurative_density", "")]
        l_parts = [p for p in l_parts if p]

        if v_parts:
            lines.append(f"Voz: {', '.join(v_parts)}")
        if l_parts:
            lines.append(f"Registro: {', '.join(l_parts)}")

        # Conocimiento e Interpretación
        kn = config.get("knowledge", {})
        if kn:
            style = kn.get("interpretation_style", "")
            if style:
                lines.append(f"Estilo Interpretativo: {style}")

        # Sesgos
        bias = config.get("bias", {})
        if bias:
            fear = bias.get("fear_focus", [])
            attention = bias.get("attention_focus", [])
            parts = []
            if fear:
                parts.append(f"miedo → {', '.join(fear)}")
            if attention:
                parts.append(f"atención → {', '.join(attention)}")
            if parts:
                lines.append("Enfoque/Sesgos: " + " | ".join(parts))
        return "\n".join(lines)

    def _format_cast(self, story: Story) -> str:
        """Devuelve el elenco formateado para prompts del LLM."""
        if story.personajes_full:
            return "\n".join(
                f"- {p['name']} ({p['role']})"
                for p in story.personajes_full
                if p.get("name")
            )
        return story.protagonista

    def _format_cast_for_context(self, story: Story) -> str | None:
        """Bloque ELENCO para el narrative_context (user message). Refuerza nombres exactos."""
        if not story.personajes_full:
            return None
        lines = ["PERSONAJES EN ESCENA (usá EXACTAMENTE estos nombres, ningún otro):"]
        for p in story.personajes_full:
            name = p.get("name", "")
            role = p.get("role", "")
            if name:
                lines.append(f"- {name} ({role})" if role else f"- {name}")
        return "\n".join(lines) if len(lines) > 1 else None

    # El word_limit ahora se gestiona desde llm_beats_definition.yaml vía BeatSpecRepository

    def build_voice_system_compact(
        self,
        story: Story,
        beat_number: int = 1,
        active_rules: list[str] | None = None,
    ) -> str | None:
        """System prompt para VOZ en perfil compact. Usa solo las reglas del beat actual."""
        strategy = self._get_strategy()
        template_name = strategy.get_template_name("voice_system")
        system = self._load_prompt(template_name)
        if not system:
            return None
        rules = active_rules if active_rules is not None else story.reglas
        reglas_str = "\n".join(f"- {r}" for r in rules) if rules else "Ninguna"
        storyteller_config_block = self._build_storyteller_block(story.storyteller_config or {})
        word_limit = self._beat_repo.get_word_limit(beat_number, "entre 350 y 430 palabras")
        return system.format(
            relator=story.relator,
            atmosfera=story.atmosfera,
            protagonistas=self._format_cast(story),
            reglas=reglas_str,
            storyteller_config_block=storyteller_config_block,
            word_limit=word_limit,
        )

    def build_story_analyst_system(self, assertive: bool = False) -> str | None:
        """System prompt para story_analyst. Selecciona entre assertive y descriptive (Spec-170)."""
        if assertive:
            system = self._load_prompt("story_analyst_system_assertive.md")
            if system:
                return system
        # fallback a descriptive (compact)
        strategy = self._get_strategy()
        if strategy.variant_name == "compact":
            system = self._load_prompt("story_analyst_system_compact.md")
            return system if system else None
        return None

    def build_synopsis_mapper_system(self, story: "Story") -> str | None:
        """System prompt para el mapper. Usa estrategia para cargar el template correcto."""
        strategy = self._get_strategy()
        template_name = strategy.get_template_name("synopsis_mapper_system")
        system = self._load_prompt(template_name)
        if system:
            return system
        return self.build_system_prompt(story)

    def build_narrative_context(
        self,
        macro_beat: MacroBeat,
        beat_anchors: dict,
        prev_snapshot: str | None = None,
        story: "Story | None" = None,
    ) -> str:
        """Ensambla el narrative_context pre-baked que recibe el VOZ. Determinístico."""
        cast_block = self._format_cast_for_context(story) if story else None
        return self._nc_assembler.assemble(macro_beat, beat_anchors, prev_snapshot, cast_block=cast_block)

    def build_rule_resolver_prompt(self, story: "Story", anchors: "Optional[NarrativeAnchors]" = None) -> str:
        """Prompt para distribuir reglas y escenarios detallados."""
        import json as _json

        template = self._load_prompt("rule_resolver_compact.md")
        if not template:
            return f"Distribuye estas reglas: {story.reglas}"

        # Acts JSON: definición narrativa completa desde YAML (Spec-052)
        acts_data = [
            {
                "id": b["id"],
                "type": b["name"],
                "intent": b.get("intent", ""),
                "intensity": b.get("intensity", ""),
                "must": b.get("must", []),
                "must_not": b.get("must_not", []),
            }
            for b in self._beats_spec
        ]
        acts_json = _json.dumps(acts_data, ensure_ascii=False, indent=2)

        # Rules JSON: ID + tipo semántico + contenido (necesario para asignación inteligente)
        if story.typed_rules:
            rules_data = [
                {
                    "id": r.id,
                    "type": r.type.value if r.type else "sin_tipo",
                    "content": r.content[:100],
                }
                for r in story.typed_rules
            ]
        else:
            rules_data = [
                {"id": str(i + 1), "type": "sin_tipo", "content": r[:100]}
                for i, r in enumerate(story.reglas)
            ]
        rules_json = _json.dumps(rules_data, ensure_ascii=False, indent=2)

        # Scenarios JSON: IDs cortos ("S1", "S2"…) + orden cronológico
        scenarios = story.scenarios or []
        scenarios_data = [
            {"id": f"S{s.order_index + 1}", "order": s.order_index + 1, "name": s.name}
            for s in scenarios
        ]
        scenarios_json = _json.dumps(scenarios_data, ensure_ascii=False, indent=2)

        # Anchors (opcional) — 5 pilares de resonancia (Spec-081)
        anchors_json = "{}"
        if anchors:
            anchors_data = {
                "resonance_hamartia": anchors.resonance_hamartia,
                "resonance_hybris": anchors.resonance_hybris,
                "resonance_anagnorisis": anchors.resonance_anagnorisis,
                "resonance_peripeteia": anchors.resonance_peripeteia,
                "resonance_residual": anchors.resonance_residual,
            }
            anchors_json = _json.dumps(anchors_data, ensure_ascii=False, indent=2)

        return template.format(
            acts_json=acts_json,
            rules_json=rules_json,
            scenarios_json=scenarios_json,
            anchors_json=anchors_json,
        )

    def build_rule_resolver_system(self) -> str | None:
        """System prompt para el rule resolver."""
        strategy = self._get_strategy()
        template_name = strategy.get_template_name("rule_resolver_system")
        return self._load_prompt(template_name)

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
        journal_template = self._load_prompt(settings.prompt_file_journal)

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

        if journal_template:
            return journal_template.format(
                title=story.title,
                protagonistas=self._format_cast(story),
                atmosfera=story.atmosfera,
                previous_state_section=previous_state_section,
                beat_number=beat.number,
                beat_summary=beat.summary,
                beat_content=beat.content[:800] if beat.has_content() else "[Aún no generado]",
                consistency_rules=consistency_rules,
            )

        estado_anterior = (
            previous_state_section if previous_state_section else "(Sin estado anterior)"
        )
        return f"""Eres el diario de memoria de una historia de terror. Registras lo que ocurre.

HISTORIA: {story.title}
BEAT #{beat.number}: {beat.summary}
CONTENIDO: {beat.content[:800] if beat.has_content() else "[Aún no generado]"}

{estado_anterior}

Responde SOLO con este JSON exacto:
{{
    "last_events": "Resumen de lo que pasó en 1-2 oraciones",
    "unresolved_mysteries": "Nuevas pistas sin responder (o vacío)",
    "physical_emotional_state": "Cómo se sienten los personajes"
}}
"""
