"""Catálogo de géneros para el wizard (Spec-440 §2). Solo lectura."""

from fastapi import APIRouter, Depends

from src.application.use_cases.list_genres import ListGenresUseCase
from src.domain.models import Genre
from src.infrastructure.database.repositories import SQLGenreRepository

router = APIRouter(tags=["Catalog"])


def get_list_genres_use_case() -> ListGenresUseCase:
    return ListGenresUseCase(SQLGenreRepository())


@router.get("/catalog/genres", response_model=list[Genre])
async def list_genres(use_case: ListGenresUseCase = Depends(get_list_genres_use_case)):
    """`[{id, label, subgenres: [{id, label}]}]`, ordenado por `order_index`."""
    return await use_case.execute()
