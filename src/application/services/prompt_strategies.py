"""Estrategias de formateo de prompts según perfil del LLM."""

from abc import ABC, abstractmethod


class IPromptStrategy(ABC):
    """Interfaz para estrategias de construcción de prompts."""

    @property
    @abstractmethod
    def variant_name(self) -> str:
        """Nombre de la variante (compact, frontier, etc)."""
        pass

    @property
    @abstractmethod
    def max_context_chars(self) -> int:
        """Máximo de caracteres para el contexto anterior."""
        pass

    @abstractmethod
    def format_context_section(
        self, previous_context: str, journal_context: str, beat_number: int
    ) -> str:
        """Formatea la sección de contexto (pasado + journal)."""
        pass

    @abstractmethod
    def get_template_name(self, base_name: str) -> str:
        """Resuelve el nombre del archivo de template (ej. voice.md -> voice_compact.md)."""
        pass

    @abstractmethod
    def format_beat_metadata(self, intensity: str, success_signal: str, state_change: dict) -> str:
        """Formatea metadatos narrativos adicionales del beat."""
        pass


class FrontierStrategy(IPromptStrategy):
    """Estrategia para modelos grandes/frontier (detallada)."""

    @property
    def variant_name(self) -> str:
        return "frontier"

    @property
    def max_context_chars(self) -> int:
        return 150  # Menos contexto directo, más foco en prosa

    def format_context_section(
        self, previous_context: str, journal_context: str, beat_number: int
    ) -> str:
        if beat_number == 1:
            return ""
        return (
            f"## CONTEXTO ANTERIOR\n{previous_context}\n\n"
            f"## MEMORIA NARRATIVA (Journal)\n{journal_context}"
        )

    def get_template_name(self, base_name: str) -> str:
        # Frontier suele usar los templates base sin sufijo
        return f"{base_name}.md"

    def format_beat_metadata(self, intensity: str, success_signal: str, state_change: dict) -> str:
        lines = [f"- Intensidad dramática: {intensity.upper()}"]
        if success_signal:
            lines.append(f"- Objetivo de resolución: {success_signal}")
        if state_change:
            lines.append(f"- Arco: {state_change.get('from', '')} -> {state_change.get('to', '')}")
        return "\n".join(lines)


class CompactStrategy(IPromptStrategy):
    """Estrategia para modelos compactos/rápidos (estructurada y densa)."""

    @property
    def variant_name(self) -> str:
        return "compact"

    @property
    def max_context_chars(self) -> int:
        return 500  # Más contexto para compensar ventana pequeña

    def format_context_section(
        self, previous_context: str, journal_context: str, beat_number: int
    ) -> str:
        if beat_number == 1:
            return ""
        return (
            f"--- LO QUE PASÓ ANTES ---\n{previous_context}\n\n"
            f"--- ESTADO DEL RELATO ---\n{journal_context}"
        )

    def get_template_name(self, base_name: str) -> str:
        return f"{base_name}_compact.md"

    def format_beat_metadata(self, intensity: str, success_signal: str, state_change: dict) -> str:
        parts = [f"INTENSIDAD: {intensity}"]
        if success_signal:
            parts.append(f"META: {success_signal}")
        if state_change:
            parts.append(f"CAMBIO: {state_change.get('from', '')}>>{state_change.get('to', '')}")
        return " | ".join(parts)
