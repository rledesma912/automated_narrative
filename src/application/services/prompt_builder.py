"""PromptBuilder - construye los prompts para el LLM."""

from pathlib import Path

from src.config import settings
from src.domain.models import Beat, NarrativeJournal, Story


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
            return self._system_template.format(
                atmosfera=story.atmosfera,
                relator=story.relator,
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

        if self._planner_template:
            return self._planner_template.format(
                title=story.title,
                protagonistas=story.protagonista,
                escenarios=story.escenarios,
                sinopsis=story.sinopsis,
                atmosfera=story.atmosfera,
                num_beats=num_beats,
            )

        return f"""Crea exactamente {num_beats} beats para esta historia de terror:

Título: {story.title}
Protagonistas: {story.protagonista}
Escenarios: {story.escenarios}
Sinopsis: {story.sinopsis}
Atmósfera: {story.atmosfera}

REGLAS OBLIGATORIAS:
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

    def build_beat_prompt(self, story: Story, beat: Beat, previous_content: str = "") -> str:
        """Build el prompt para narrar un beat (usa voice.md o fallback)."""
        if self._voice_template is None:
            self._voice_template = self._load_prompt(settings.prompt_file_voice)

        if self._voice_template:
            return self._voice_template.format(
                beat_summary=beat.summary,
            )

        base = f"""NARRA EL BEAT #{beat.number}:
{beat.summary}

Contexto:
- Protagonistas: {story.protagonista}
- Escenario: {story.escenarios}
- Atmósfera: {story.atmosfera}

Extiende este momento (150-400 palabras)."""

        if previous_content:
            base += f"\n\nLo que pasó antes:\n{previous_content}"

        return base

    def build_voice_prompt(self, story: Story) -> str:
        """Build el system prompt para la Voz (usa voice.md o fallback)."""
        if self._voice_template is None:
            self._voice_template = self._load_prompt(settings.prompt_file_voice)

        if self._voice_template:
            reglas_str = "\n".join([f"- {r}" for r in story.reglas]) if story.reglas else "Ninguna"
            return self._voice_template.format(
                relator=story.relator,
                protagonistas=story.protagonista,
                escenarios=story.escenarios,
                atmosfera=story.atmosfera,
                sinopsis=story.sinopsis,
                previous_context="",
                beat_number=0,
                beat_summary="",
            ).split("## CONTEXTO ANTERIOR")[0]

        reglas_str = "\n".join([f"- {r}" for r in story.reglas]) if story.reglas else "Ninguna"

        return f"""Eres la Voz narrativa de una historia de terror.
Tu estilo: {story.atmosfera}
El relator: {story.relator}

REGLAS:
{reglas_str}

Instrucciones:
- Escribe en primera persona
- Usa lenguaje natural, no formal
- Extiende cada momento (150-400 palabras)
- Siente los detalles: sonidos, olores, texturas
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
                protagonists=story.protagonista,
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
