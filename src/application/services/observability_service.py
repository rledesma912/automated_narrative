import logging
from dataclasses import asdict, dataclass
from typing import List, Optional

from src.utils.timezone import now_argentina

logger = logging.getLogger(__name__)


@dataclass
class SystemEvent:
    timestamp: str
    type: str  # 'info', 'success', 'error', 'warning'
    category: str  # 'generation', 'export', 'database', 'system'
    message: str
    story_id: Optional[str] = None
    story_title: Optional[str] = None


class ObservabilityService:
    _instance = None
    _events: List[SystemEvent] = []
    _max_events = 50

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ObservabilityService, cls).__new__(cls)
        return cls._instance

    def record(
        self,
        category: str,
        message: str,
        type: str = "info",
        story_id: Optional[str] = None,
        story_title: Optional[str] = None,
    ):
        event = SystemEvent(
            timestamp=now_argentina().strftime("%H:%M:%S"),
            type=type,
            category=category,
            message=message,
            story_id=story_id,
            story_title=story_title,
        )
        self._events.insert(0, event)
        if len(self._events) > self._max_events:
            self._events.pop()

        log_msg = f"[{category.upper()}] {message}"
        if story_id:
            log_msg += f" (Story: {story_id})"
        logger.info(log_msg)

    def get_latest(self) -> Optional[SystemEvent]:
        return self._events[0] if self._events else None

    def get_history(self, limit: int = 10) -> List[dict]:
        return [asdict(e) for e in self._events[:limit]]


# Instancia global
observability = ObservabilityService()
