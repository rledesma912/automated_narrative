class NarrativeError(Exception):
    """Error base para el dominio narrativo."""
    pass

class QualityValidationError(NarrativeError):
    """Error lanzado cuando un relato no cumple los estándares de calidad."""
    def __init__(self, message: str, word_count: int):
        super().__init__(message)
        self.word_count = word_count
