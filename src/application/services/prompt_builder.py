"""PromptBuilder - construye los prompts para el LLM."""

import logging
from pathlib import Path

from src.config import settings
from src.domain.models import Beat, NarrativeJournal, Story

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Servicio para construir prompts."""

    def __init__(self, prompts_dir: str | None = None):
        self.prompts_dir = Path(prompts_dir or settings.prompts_dir)
        self._system_template = None
        self._planner_template = None
        self._voice_template = None
        self._journal_template = None

    def _load_prompt(self, filename: str) -> str:
        """Carga una plantilla de prompt."""
        file_path = self.prompts_dir / filename
        if file_path.exists():
            return file_path.read_text(encoding="utf-8").strip()
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

    def build_planner_prompt(self, story: Story, num_beats: int = 8) -> str:
        """Build el prompt del Director para generar la escaleta."""
        if self._planner_template is None:
            self._planner_template = self._load_prompt(
                "planner"
            )  # Fallback uses dynamic generation

        reglas_str = "\n".join([f"- {r}" for r in story.reglas]) if story.reglas else "Ninguna"

        if self._planner_template:
            return self._planner_template.format(
                title=story.title,
                protagonistas=story.protagonista,
                escenarios=story.escenarios,
                sinopsis=story.sinopsis,
                atmosfera=story.atmosfera,
                num_beats=num_beats,
                reglas=reglas_str,
            )

        return f"""Crea exactamente {num_beats} beats para esta historia de terror:

Título: {story.title}
Protagonistas: {story.protagonista}
Escenarios: {story.escenarios}
Sinopsis: {story.sinopsis}
Atmósfera: {story.atmosfera}

REGLAS DE LA HISTORIA:
{reglas_str}

REGLAS OBLIGATORIAS:
- CADA beat debe respetar las reglas arriba.
- Genera EXACTAMENTE {num_beats} beats
- Cada beat debe ser una línea que empieza con el número: "1.", "2.", etc
- No generes más de {num_beats} beats
- Formato: "n. Título del beat" (una línea por beat)

Responde solo con {num_beats} líneas numeradas."""

    def _build_narrative_planner_prompt(self, story: Story) -> str:
        """Build el prompt del Director para 6 beats narrativos."""
        narrative_template = self._load_prompt("planner_prompt_narrative.md")

        if narrative_template:
            return narrative_template.format(
                sinopsis=story.sinopsis[:200],  # Limit sinopsis length
                protagonista=story.protagonista[:100],  # Limit protagonista
            )

        return f"""Responde solo con 6 líneas numeradas:
1. Apertura: ...
2. Incidente: ...
3. Subida: ...
4. Crisis: ...
5. Cumbre: ...
6. Desenlace: ...

Historia: {story.sinopsis[:200]}"""

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

    def _build_previous_context(self, previous_beats: list[Beat] | None) -> str:
        """Construye el contexto de beats anteriores."""
        if not previous_beats:
            return "Sin contexto anterior"

        completed = [b for b in previous_beats if b.status == "completed" and b.content]
        if not completed:
            return "Sin contexto anterior"

        last_2 = completed[-2:]
        context_parts = []
        for b in last_2:
            content = b.content[:150] + "..." if len(b.content) > 150 else b.content
            context_parts.append(f"Beat #{b.number}: {content}")

        return "\n\n".join(context_parts)

    def build_beat_prompt(
        self,
        story: Story,
        beat: Beat,
        previous_beats: list[Beat] | None = None,
        journal: NarrativeJournal | None = None,
        total_beats: int = 10,
    ) -> str:
        """Build el prompt para narrar un beat con contexto completo."""
        if self._voice_template is None:
            self._voice_template = self._load_prompt(settings.prompt_file_voice)

        previous_context = self._build_previous_context(previous_beats)
        journal_context = self._build_journal_context(journal)
        persona = self._get_persona_gramatical(story.relator)
        reglas_str = "\n".join([f"- {r}" for r in story.reglas]) if story.reglas else "Ninguna"

        logger.debug(
            f"[PB] relator={story.relator}, persona={persona}, beat={beat.number}/{total_beats}"
        )
        logger.debug(
            f"[PB] prev_beats={len(previous_beats) if previous_beats else 0}, journal={'yes' if journal else 'None'}"
        )

        if self._voice_template:
            prompt = self._voice_template.format(
                title=story.title,
                relator=story.relator,
                persona_gramatical=persona,
                atmosphere=story.atmosfera,
                protagonistas=story.protagonista,
                escenarios=story.escenarios,
                sinopsis=story.sinopsis,
                beat_number=beat.number,
                total_beats=total_beats,
                beat_summary=beat.summary,
                previous_context=previous_context,
                journal_context=journal_context,
                reglas=reglas_str,
            )
            logger.debug(f"[PB] prompt (first 800 chars):\n{prompt[:800]}")
            return prompt

        base = f"""NARRA EL BEAT #{beat.number} de {total_beats}:
{beat.summary}

Contexto:
- Título: {story.title}
- Protagonistas: {story.protagonista}
- Escenario: {story.escenarios}
- Atmósfera: {story.atmosfera}
- Relator: {story.relator} ({persona})
- Sinopsis: {story.sinopsis}

Extiende este momento (150-400 palabras)."""

        if previous_context and previous_context != "Sin contexto anterior":
            base += f"\n\nLo que pasó antes:\n{previous_context}"

        if journal_context and journal_context != "Sin memoria narrativa aún":
            base += f"\n\nMemoria narrativa:\n{journal_context}"

        return base

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

    def build_journal_prompt(
        self,
        story: Story,
        beat: Beat,
        previous_journal: "NarrativeJournal | None" = None,
    ) -> str:
        """Build el prompt para actualizar el journal (usa journal.md o fallback)."""
        if self._journal_template is None:
            self._journal_template = self._load_prompt(settings.prompt_file_journal)

        prev_last_events = (
            previous_journal.last_events if previous_journal else "Sin eventos registrados"
        )
        prev_unresolved = (
            previous_journal.unresolved_mysteries if previous_journal else "Sin misterios"
        )
        prev_state = (
            previous_journal.physical_emotional_state
            if previous_journal
            else "Sin estado registrado"
        )

        if self._journal_template:
            return self._journal_template.format(
                title=story.title,
                protagonistas=story.protagonista,
                atmosfera=story.atmosfera,
                prev_last_events=prev_last_events,
                prev_unresolved_mysteries=prev_unresolved,
                prev_physical_emotional_state=prev_state,
                beat_number=beat.number,
                beat_summary=beat.summary,
                beat_content=beat.content[:800] if beat.content else "[Aún no generado]",
            )

        return f"""Eres el diario de memoria de una historia de terror. Registras lo que ocurre.

HISTORIA: {story.title}
BEAT #{beat.number}: {beat.summary}
CONTENIDO: {beat.content[:800] if beat.content else "[Aún no generado]"}

REGISTRO ANTERIOR:
- Últimos eventos: {prev_last_events}
- Misterios sin resolver: {prev_unresolved}
- Estado físico/emocional: {prev_state}

Responde SOLO con este JSON exacto:
{{
    "last_events": "Resumen de lo que pasó en 1-2 oraciones",
    "unresolved_mysteries": "Nuevas pistas sin responder (o vacío)",
    "physical_emotional_state": "Cómo se sienten los personajes"
}}
"""
