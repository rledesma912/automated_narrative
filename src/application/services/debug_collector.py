"""DebugCollector — acumula llamadas LLM para generar el archivo de diagnóstico."""

import inspect
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class LLMCallRecord:
    role: str
    beat_number: int | None
    source_component: str
    model: str
    temperature: float
    num_ctx: int | None
    num_predict: int | None
    system_prompt: str | None
    user_prompt: str
    raw_response: str
    normalized_response: str
    parser_result: str
    elapsed_s: float
    narrative_context: str | None = None
    system_prompt_file: str | None = None
    user_prompt_file: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)


class DebugCollector:
    """Acumula LLMCallRecord durante una sesión de generación."""

    def __init__(self, active: bool = True):
        self._active = active
        self.records: list[LLMCallRecord] = []
        self._session_start: datetime = datetime.now()

    def is_active(self) -> bool:
        return self._active

    def record(
        self,
        *,
        role: str,
        beat_number: int | None,
        source_component: str,
        model: str,
        temperature: float,
        num_ctx: int | None,
        num_predict: int | None,
        system_prompt: str | None,
        user_prompt: str,
        raw_response: str,
        normalized_response: str,
        parser_result: str,
        elapsed_s: float,
        narrative_context: str | None = None,
        system_prompt_file: str | None = None,
        user_prompt_file: str | None = None,
    ) -> None:
        self.records.append(
            LLMCallRecord(
                role=role,
                beat_number=beat_number,
                source_component=source_component,
                model=model,
                temperature=temperature,
                num_ctx=num_ctx,
                num_predict=num_predict,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                raw_response=raw_response,
                normalized_response=normalized_response,
                parser_result=parser_result,
                elapsed_s=elapsed_s,
                narrative_context=narrative_context,
                system_prompt_file=system_prompt_file,
                user_prompt_file=user_prompt_file,
            )
        )

    def write(self, output_dir: Path, story_meta: dict) -> Path:
        from src.infrastructure.renderers.debug_renderer import DebugMarkdownRenderer

        renderer = DebugMarkdownRenderer()
        return renderer.render(self.records, story_meta, output_dir, self._session_start)

    @staticmethod
    def source_label(caller: object) -> str:
        """Resuelve 'ClassName (filename.py)' en runtime sin hardcoding."""
        try:
            filename = Path(inspect.getfile(type(caller))).name
        except (TypeError, OSError):
            filename = "unknown"
        return f"{type(caller).__name__} ({filename})"


class NullDebugCollector(DebugCollector):
    """Implementación no-op: costo cero cuando --debug no está activo."""

    def __init__(self) -> None:
        super().__init__(active=False)

    def record(self, **kwargs) -> None:  # type: ignore[override]
        pass

    def write(self, output_dir: Path, story_meta: dict) -> Path:
        return output_dir
