"""Markdown renderer."""

from src.domain.models import Story


class MarkdownRenderer:
    """Renders story to Markdown."""

    def render(self, story: Story) -> str:
        """Render story to Markdown."""
        md = f"# {story.title}\n\n"

        md += f"**Protagonistas:** {story.protagonista}\n"
        md += f"**Relator:** {story.relator}\n"
        md += f"**Escenario:** {story.escenarios}\n"
        md += f"**Atmósfera:** {story.atmosfera}\n\n"

        md += f"_{story.sinopsis}_\n\n"
        md += "---\n\n"

        sorted_beats = sorted(story.beats, key=lambda b: b.number)

        for beat in sorted_beats:
            md += f"## {beat.number}. {beat.summary}\n\n"
            md += beat.content + "\n\n"

        return md
