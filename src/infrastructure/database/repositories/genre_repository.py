"""Repositorio del catálogo de géneros (Spec-440 §2) y naturalezas de entidad (Spec-450 §1)."""

from src.domain.models import EntityNature, Genre, Subgenre
from src.infrastructure.database.connection import get_connection


class SQLGenreRepository:
    """Lee `genre` / `subgenre` / `entity_nature`. El catálogo se siembra en `init_db()`."""

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
            cursor = await conn.execute(f"{_NATURES_SELECT} ORDER BY gn.genre_id, n.order_index")
            for r in await cursor.fetchall():
                genre = genres.get(r["genre_id"])
                if genre is not None:
                    genre.entity_natures.append(EntityNature(id=r["id"], label=r["label"]))
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

    async def natures_of(self, genre_id: str) -> list[EntityNature]:
        conn = await get_connection()
        try:
            cursor = await conn.execute(
                f"{_NATURES_SELECT} WHERE gn.genre_id = ? ORDER BY n.order_index", (genre_id,)
            )
            return [EntityNature(id=r["id"], label=r["label"]) for r in await cursor.fetchall()]
        finally:
            await conn.close()

    async def nature_allowed(self, genre_id: str, nature_id: str) -> bool:
        conn = await get_connection()
        try:
            if genre_id:
                cursor = await conn.execute(
                    "SELECT 1 FROM genre_entity_nature WHERE genre_id = ? AND nature_id = ?",
                    (genre_id, nature_id),
                )
            else:
                cursor = await conn.execute(
                    "SELECT 1 FROM entity_nature WHERE id = ?", (nature_id,)
                )
            return await cursor.fetchone() is not None
        finally:
            await conn.close()


_NATURES_SELECT = (
    "SELECT gn.genre_id, n.id, n.label FROM genre_entity_nature gn "
    "JOIN entity_nature n ON n.id = gn.nature_id"
)
