"""Markdown renderer."""

from src.domain.models import Story


class MarkdownRenderer:
    """Renders story to Markdown."""

    def render(self, story: Story) -> str:
        """Render story to Markdown."""
        md = f"# {story.title}\n\n"

        sorted_beats = sorted(story.beats, key=lambda b: b.number)

        seen_numbers = set()
        for beat in sorted_beats:
            if beat.number in seen_numbers:
                continue
            seen_numbers.add(beat.number)

            md += f"## Acto {beat.number}\n\n"
            if beat.content:
                md += beat.content + "\n\n"

        return md
