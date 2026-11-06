"""El contexto de una llamada al LLM: de qué job y de qué acto (Spec-740).

Viaja en un `ContextVar` para no cambiar la firma de `LLMProvider.generate`. Cada job es
una `asyncio.Task` propia (`JobManager._run`) y las tareas que lanza heredan una copia, así
que dos jobs simultáneos no se pisan. Fuera de un job (CLI, tests) no hay contexto.
"""

from contextvars import ContextVar
from dataclasses import dataclass, replace
from uuid import UUID


@dataclass(frozen=True)
class LLMContext:
    job_id: UUID
    story_id: UUID
    act: int | None = None


_current: ContextVar[LLMContext | None] = ContextVar("llm_context", default=None)


def current() -> LLMContext | None:
    """El contexto de la tarea actual, o None fuera de un job."""
    return _current.get()


def enter_job(job_id: UUID, story_id: UUID) -> None:
    """Marca la tarea actual como parte de este job (sin acto)."""
    _current.set(LLMContext(job_id=job_id, story_id=story_id))


def set_act(act: int | None) -> None:
    """Las llamadas que siguen son de este acto. Sin job, no hace nada."""
    context = _current.get()
    if context is not None:
        _current.set(replace(context, act=act))
