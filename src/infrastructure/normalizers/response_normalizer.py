import re
from typing import List, Protocol
from src.config import settings

class NormalizationStrategy(Protocol):
    """Interfaz para estrategias de normalización de respuestas de LLM."""
    def clean(self, text: str) -> str:
        ...

class ThoughtTagStripper:
    """Elimina etiquetas de pensamiento profundo (ej: <think>...</think>)."""
    def __init__(self, tags: List[str]):
        self.tags = tags

    def clean(self, text: str) -> str:
        cleaned_text = text
        for tag in self.tags:
            pattern = rf'<{tag}>.*?(?:</{tag}>|$)'
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.DOTALL)
        return cleaned_text

class MarkdownExtractor:
    """Extrae contenido narrativo de bloques de código markdown."""
    def clean(self, text: str) -> str:
        pattern = r'```(?:markdown|text)?\s*(.*?)\s*```'
        match = re.search(pattern, text, flags=re.DOTALL)
        return match.group(1) if match else text

class ClutterRemover:
    """Elimina patrones de ruido (explicaciones del modelo)."""
    def __init__(self, patterns: List[str]):
        self.patterns = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in patterns]

    def clean(self, text: str) -> str:
        cleaned_text = text
        for pattern in self.patterns:
            cleaned_text = pattern.sub('', cleaned_text)
        return cleaned_text

class LLMResponseNormalizer:
    """Orquestador que normaliza la respuesta cruda del LLM a un formato estándar."""
    def __init__(self, model_name: str = "default"):
        rules = settings.sanitization
        self.strategies: List[NormalizationStrategy] = []
        
        self.strategies.append(ThoughtTagStripper(tags=rules.thinking_tags))
        
        if rules.markdown_extraction_enabled:
            self.strategies.append(MarkdownExtractor())
            
        if rules.noise_patterns:
            self.strategies.append(ClutterRemover(patterns=rules.noise_patterns))

    def normalize(self, raw_text: str) -> str:
        """Aplica todas las estrategias y devuelve el texto limpio."""
        clean_text = raw_text
        for strategy in self.strategies:
            clean_text = strategy.clean(clean_text)
        
        return clean_text.strip()
