"""Repositorio del catálogo de géneros (Spec-440 §2)."""

from src.domain.models import Genre, Subgenre
from src.infrastructure.database.connection import get_connection


class SQLGenreRepository:
    """Lee `genre` / `subgenre`. El catálogo se siembra en `init_db()`."""

    async def list_with_subgenres(self) -> list[Genre]:
        conn = await get_connection()
        try:
            cursor = await conn.execute("SELECT id, label FROM genre ORDER BY order_index")
            genres = {r["id"]: Genre(id=r["id"], label=r["label"]) for r in await cursor.fetchall()}
            cursor = await conn.execute(
                "SELECT genre_id, id, label FROM subgenre ORDER BY genre_id, order_index"
            )
            for r in await cursor.fetchall():
                genre = genres.get(r["genre_id"])
                if genre is not None:
                    genre.subgenres.append(Subgenre(id=r["id"], label=r["label"]))
        finally:
            await conn.close()
        return list(genres.values())

    async def exists(self, genero: str, subgenero: str = "") -> bool:
        if not genero:
            return not subgenero
        conn = await get_connection()
        try:
            if subgenero:
                cursor = await conn.execute(
                    "SELECT 1 FROM subgenre WHERE genre_id = ? AND id = ?", (genero, subgenero)
                )
            else:
                cursor = await conn.execute("SELECT 1 FROM genre WHERE id = ?", (genero,))
            return await cursor.fetchone() is not None
        finally:
            await conn.close()
