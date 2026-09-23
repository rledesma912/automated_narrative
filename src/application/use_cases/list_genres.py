"""ListGenresUseCase - catálogo de géneros con sus subgéneros (Spec-440 §2)."""

from src.domain.interfaces import GenreRepository
from src.domain.models import Genre


class ListGenresUseCase:
    """Caso de uso para listar el catálogo de géneros."""

    def __init__(self, genre_repository: GenreRepository):
        self.genre_repository = genre_repository

    async def execute(self) -> list[Genre]:
        """Géneros y subgéneros ordenados por `order_index`."""
        return await self.genre_repository.list_with_subgenres()
