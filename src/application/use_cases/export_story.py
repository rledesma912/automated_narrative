from pathlib import Path
from uuid import UUID

from src.config import settings
from src.domain.interfaces import StoryRepository
from src.infrastructure.renderers.markdown_renderer import MarkdownRenderer


class ExportStoryUseCase:
    """Caso de uso encargado de ensamblar y guardar el relato final."""

    def __init__(self, repository: StoryRepository, renderer: MarkdownRenderer):
        self.repository = repository
        self.renderer = renderer
        self.output_dir = Path(settings.output_dir)
        self.output_dir.mkdir(exist_ok=True)

    async def execute(self, story_id: UUID) -> str:
        """Ensambla el relato y devuelve el path del archivo generado."""

        # 1. Obtener datos de la DB
        story = await self.repository.get_story(story_id)
        if not story:
            raise ValueError(f"Historia {story_id} no encontrada.")

        acts = await self.repository.get_acts(story_id)
        if not acts:
            raise ValueError(f"La historia {story_id} no tiene actos generados.")

        # Ordenar actos por número por si acaso
        acts.sort(key=lambda x: x.number)

        # 2. Renderizar Markdown
        md_content = self.renderer.render_story(story, acts)

        # 3. Guardar archivo físico
        # Usamos el título para el nombre del archivo (limpiando caracteres raros)
        safe_title = "".join([c if c.isalnum() else "_" for c in story.title]).strip("_")
        file_path = self.output_dir / f"{safe_title}_{str(story_id)[:8]}.md"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        return str(file_path)
