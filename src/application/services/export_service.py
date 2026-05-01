"""ExportService — renderiza y persiste el MD de la historia (Spec-205 B2)."""

import logging
import re
from pathlib import Path

from src.domain.models import MacroBeat, Story
from src.infrastructure.renderers import MarkdownRenderer
from src.utils.timezone import now_argentina

logger = logging.getLogger(__name__)

_DEFAULT_OUTPUT_DIR = Path("frontend/public/output_stories")


class ExportService:
    def __init__(self, output_dir: Path | None = None):
        self._output_dir = output_dir or _DEFAULT_OUTPUT_DIR
        self._renderer = MarkdownRenderer()

    async def export(self, story: Story, beats: list[MacroBeat]) -> str:
        """Renderiza el relato a MD, lo escribe en disco y retorna el path relativo.

        El path relativo (ej: output_stories/titulo_20240101_120000.md) se persiste
        en la columna file_path de story y se sirve estáticamente desde Express.
        """
        story.beats = beats
        md = self._renderer.render(story)

        self._output_dir.mkdir(parents=True, exist_ok=True)

        slug = re.sub(r"[^a-z0-9]+", "_", story.title.lower()).strip("_")
        date_str = now_argentina().strftime("%Y%m%d_%H%M%S")
        filename = f"{slug}_{date_str}.md"

        (self._output_dir / filename).write_text(md, encoding="utf-8")
        logger.info("[EXPORT] MD generado: %s", filename)

        return f"output_stories/{filename}"
