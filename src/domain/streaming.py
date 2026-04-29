"""Streaming DTOs for SSE communication (Spec-201)."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class StreamEventType(str, Enum):
    STATUS    = "status"
    ANCHORS   = "anchors"
    BEAT_START = "beat_start"
    BEAT_DONE  = "beat_done"
    HEARTBEAT  = "heartbeat"
    ERROR      = "stream_error"  # "error" es reservado por EventSource en el browser
    DONE       = "done"


class StreamEvent(BaseModel):
    event: StreamEventType
    data: dict | str
    timestamp: datetime = Field(default_factory=datetime.now)

    def to_sse(self) -> dict:
        """Formato compatible con sse-starlette EventSourceResponse."""
        import json
        payload = self.data if isinstance(self.data, str) else json.dumps(self.data, ensure_ascii=False)
        return {"event": self.event.value, "data": payload}
