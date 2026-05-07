"""Pipeline events for phase-level observability (Spec-500 S-A).

Abstrae los eventos de fase del pipeline de generación para que CLI y SSE
consuman la misma información sin conocer detalles del otro canal.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PhaseEvent(str, Enum):
    """Eventos de fase del pipeline de generación."""

    PLAN_READY = "plan_ready"
    ANALYST_START = "analyst_start"
    ANALYST_DONE = "analyst_done"
    RESOLVER_START = "resolver_start"
    RESOLVER_DONE = "resolver_done"
    BEAT_START = "beat_start"
    MAPPER_DONE = "mapper_done"
    VOZ_DONE = "voz_done"
    JOURNAL_DONE = "journal_done"
    BEAT_COMPLETE = "beat_complete"
    STEP_START = "step_start"
    STEP_DONE = "step_done"


@dataclass
class PipelinePhaseData:
    """Datos asociados a un evento de fase del pipeline."""

    phase: PhaseEvent
    beat_number: int | None = None
    step_label: str | None = None
    elapsed_s: float | None = None
    num_beats: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convierte el evento a dict para consumo por adapters."""
        result: dict[str, Any] = {"phase": self.phase.value}
        if self.beat_number is not None:
            result["beat_number"] = self.beat_number
        if self.step_label is not None:
            result["step_label"] = self.step_label
        if self.elapsed_s is not None:
            result["elapsed_s"] = round(self.elapsed_s, 3)
        if self.num_beats is not None:
            result["num_beats"] = self.num_beats
        result.update(self.extra)
        return result
