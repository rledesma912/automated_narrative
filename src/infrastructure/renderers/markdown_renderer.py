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

        if story.reglas:
            md += "**Reglas:**\n"
            for regla in story.reglas:
                md += f"- {regla}\n"
            md += "\n"

        md += "---\n\n"

        sorted_beats = sorted(story.beats, key=lambda b: b.number)

        seen_numbers = set()
        for beat in sorted_beats:
            if beat.number in seen_numbers:
                continue
            seen_numbers.add(beat.number)

            md += f"## {beat.number}. {beat.summary}\n\n"
            if beat.content:
                md += beat.content + "\n\n"

        return md
