import re
from src.domain.exceptions import QualityValidationError

class QualityValidator:
    """Validador de estándares narrativos y técnicos."""
    
    def __init__(self, min_words: int = 300, max_residue_patterns: list[str] = None):
        self.min_words = min_words
        # Patrones de basura comunes que NO deberían estar en el texto limpio
        self.residue_patterns = max_residue_patterns or [
            r'<(think|thought|reasoning)>', # Tags técnicos
            r'\{.*\}',                      # JSON residual
            r'```'                          # Bloques de código markdown
        ]

    def validate(self, text: str) -> bool:
        """Valida longitud y ausencia de ruido técnico."""
        
        # 1. Validación de Longitud (Conteo de palabras)
        word_count = len(text.split())
        if word_count < self.min_words:
            raise QualityValidationError(
                f"El relato es demasiado corto: {word_count} palabras (mínimo {self.min_words}).",
                word_count=word_count
            )
            
        # 2. Validación de Residuos Técnicos
        for pattern in self.residue_patterns:
            if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL):
                raise QualityValidationError(
                    f"El relato contiene residuos técnicos no deseados (patrón: {pattern}).",
                    word_count=word_count
                )
        
        return True
