import pytest
from src.infrastructure.normalizers.response_normalizer import LLMResponseNormalizer

def test_normalizer_removes_thinking_tags():
    """Valida que el stripper elimine bloques <think> de forma efectiva."""
    normalizer = LLMResponseNormalizer()
    
    raw_text = """
<think>
El usuario quiere una historia de terror. 
</think>
Había una vez un bosque oscuro...
"""
    clean_text = normalizer.normalize(raw_text)
    
    assert "think" not in clean_text
    assert clean_text == "Había una vez un bosque oscuro..."

def test_normalizer_removes_markdown_blocks():
    """Valida que extraiga solo el texto dentro de bloques de código markdown."""
    normalizer = LLMResponseNormalizer()
    
    raw_text = """
Aquí tienes el relato:
```markdown
El viento soplaba fuerte.
```
"""
    clean_text = normalizer.normalize(raw_text)
    
    assert "Aquí tienes" not in clean_text
    assert "```markdown" not in clean_text
    assert clean_text == "El viento soplaba fuerte."

def test_normalizer_chain_full():
    """Valida la cadena completa: pensamiento + markdown."""
    normalizer = LLMResponseNormalizer()
    
    raw_text = """
<think>Plan...</think>
```
El horror acechaba.
```
"""
    clean_text = normalizer.normalize(raw_text)
    
    assert clean_text == "El horror acechaba."
