"""ResponseNormalizer — limpieza de respuestas LLM antes de usarlas en el pipeline."""

import re

from src.config import settings


class ResponseNormalizer:
    """Limpia el output raw del LLM eliminando ruido estructural y técnico.

    Lee su configuración de llm_core_definitions.yaml via settings.
    Se puede instanciar con config custom para tests (DI).
    """

    def __init__(self, config: dict | None = None, role: str | None = None):
        cfg = config if config is not None else settings.llm_response_filter_config
        self._thinking_tags: list[str] = cfg.get("thinking_tags", [])
        self._strip_patterns: list[str] = cfg.get("strip_line_patterns", [])
        self._preserve_paragraphs: bool = cfg.get("preserve_paragraph_breaks", True)
        self._model_overrides: dict = cfg.get("model_overrides", {})
        self._role_overrides: dict = cfg.get("role_overrides", {})

        if role:
            role_override = self._get_role_override(role)
            self._strip_patterns = role_override.get("strip_line_patterns", self._strip_patterns)

    def normalize(self, text: str, model_name: str = "") -> str:
        """Aplica todos los filtros y retorna texto limpio."""
        result = self._strip_thinking_tags(text)
        result = self._strip_noisy_lines(result, model_name)
        result = self._clean_whitespace(result)
        return result.strip()

    def _strip_thinking_tags(self, text: str) -> str:
        """Elimina bloques <think>...</think> y similares con su contenido."""
        for tag in self._thinking_tags:
            pattern = rf"<{re.escape(tag)}>.*?</{re.escape(tag)}>"
            text = re.sub(pattern, "", text, flags=re.DOTALL | re.IGNORECASE)
        return text

    def _strip_noisy_lines(self, text: str, model_name: str) -> str:
        """Elimina líneas que coincidan con los patrones de ruido."""
        patterns = list(self._strip_patterns)

        # Agregar patrones extra del override de modelo si aplica
        override = self._get_model_override(model_name)
        patterns += override.get("strip_line_patterns_extra", [])

        if not patterns:
            return text

        compiled = [re.compile(p) for p in patterns]
        lines = text.split("\n")
        clean_lines = [line for line in lines if not any(rx.search(line) for rx in compiled)]
        return "\n".join(clean_lines)

    def _clean_whitespace(self, text: str) -> str:
        """Normaliza espacios en blanco preservando saltos de párrafo si está configurado."""
        if self._preserve_paragraphs:
            # Colapsa 3+ líneas vacías consecutivas a una sola línea vacía
            text = re.sub(r"\n{3,}", "\n\n", text)
            # Limpia espacios al final de cada línea
            lines = [line.rstrip() for line in text.split("\n")]
            return "\n".join(lines)
        else:
            # Modo compacto: elimina líneas vacías (comportamiento legacy)
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            return "\n".join(lines)

    def _get_model_override(self, model_name: str) -> dict:
        """Retorna el override de config para el modelo dado (por substring del nombre)."""
        model_lower = model_name.lower()
        for key, override in self._model_overrides.items():
            if key.lower() in model_lower:
                return override
        return {}

    def _get_role_override(self, role: str) -> dict:
        """Retorna el override de config para el rol dado."""
        role_lower = role.lower()
        for key, override in self._role_overrides.items():
            if key.lower() == role_lower:
                return override
        return {}
