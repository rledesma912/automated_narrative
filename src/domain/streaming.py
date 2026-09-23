"""Streaming DTOs for SSE communication (Spec-201)."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from src.utils.timezone import now_argentina


class StreamEventType(str, Enum):
    STATUS = "status"
    ANCHORS = "anchors"
    BEAT_START = "beat_start"
    BEAT_DONE = "beat_done"
    HEARTBEAT = "heartbeat"
    ERROR = "stream_error"  # "error" es reservado por EventSource en el browser
    DONE = "done"
    # Spec-460: ciclo de vida de jobs (canal global)
    JOB_STARTED = "job_started"
    JOB_PROGRESS = "job_progress"
    JOB_DONE = "job_done"
    JOB_FAILED = "job_failed"
    SNAPSHOT = "snapshot"


class StreamEvent(BaseModel):
    event: StreamEventType
    data: dict | str
    timestamp: datetime = Field(default_factory=now_argentina)
    # Spec-460: id monotónico por canal (lo asigna el EventBus) → `Last-Event-ID`.
    id: int | None = None

    def to_sse(self) -> dict:
        """Formato compatible con sse-starlette EventSourceResponse."""
        import json

        payload = (
            self.data if isinstance(self.data, str) else json.dumps(self.data, ensure_ascii=False)
        )
        sse = {"event": self.event.value, "data": payload}
        if self.id is not None:
            sse["id"] = str(self.id)
        return sse
