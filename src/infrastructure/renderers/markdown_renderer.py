from typing import List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.config import settings
from src.domain.models import GeneratedAct, Story


class MarkdownRenderer:
    """Motor de renderizado para archivos Markdown usando Jinja2."""

    def __init__(self, template_dir: str = None):
        self.env = Environment(loader=FileSystemLoader(template_dir or settings.template_dir), autoescape=select_autoescape())

    def render_story(self, story: Story, acts: List[GeneratedAct]) -> str:
        """Genera el contenido Markdown final inyectando los datos en la plantilla."""
        template = self.env.get_template("story_output.md.j2")
        return template.render(story=story, acts=acts)
