"""ExportStoryUseCase - exporta la historia a Markdown."""

from src.domain.interfaces import StoryRepository


class ExportStoryUseCase:
    """Caso de uso para exportar una historia."""

    def __init__(self, story_repository: StoryRepository):
        self.story_repository = story_repository

    async def execute(self, story_id) -> str:
        """Exporta la historia a Markdown."""
        story = await self.story_repository.get_by_id(story_id)

        if not story:
            from src.domain.exceptions import StoryNotFoundError

            raise StoryNotFoundError(str(story_id))

        md = f"# {story.title}\n\n"

        for beat in sorted(story.beats, key=lambda b: b.number):
            md += f"## {beat.number}. {beat.summary}\n\n"
            md += beat.content + "\n\n"

        return md
