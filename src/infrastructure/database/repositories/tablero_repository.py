"""SQL repository de las opiniones del tablero (Spec-795 §2.2). Anónimas, sin dueño (D1)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from src.domain.tablero import Opinion, TipoOpinion
from src.infrastructure.database.connection import connection
from src.utils.timezone import now_argentina


def _opinion(row) -> Opinion:
    return Opinion(
        id=row["id"],
        entrega=row["entrega"],
        archivo=row["archivo"],
        tipo=row["tipo"],
        texto=row["texto"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


class SQLTableroRepository:
    async def agregar(
        self, entrega: str, archivo: str, tipo: TipoOpinion, texto: str = ""
    ) -> Opinion:
        creada = now_argentina()
        async with connection() as conn:
            cursor = await conn.execute(
                """INSERT INTO tablero_opinion (entrega, archivo, tipo, texto, created_at)
                VALUES (?, ?, ?, ?, ?)""",
                (entrega, archivo, tipo, texto, creada.isoformat()),
            )
            await conn.commit()
            nuevo = cursor.lastrowid
        return Opinion(
            id=nuevo, entrega=entrega, archivo=archivo, tipo=tipo, texto=texto, created_at=creada
        )

    async def de_entrega(self, entrega: str) -> list[Opinion]:
        async with connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM tablero_opinion WHERE entrega = ? ORDER BY id", (entrega,)
            )
            rows = await cursor.fetchall()
        return [_opinion(r) for r in rows]

    async def cuentas(self) -> dict[str, int]:
        """Cuántas opiniones tiene cada entrega (para la lista)."""
        async with connection() as conn:
            cursor = await conn.execute(
                "SELECT entrega, COUNT(*) AS n FROM tablero_opinion GROUP BY entrega"
            )
            rows = await cursor.fetchall()
        return defaultdict(int, {r["entrega"]: r["n"] for r in rows})

    async def borrar(self, opinion_id: int) -> bool:
        async with connection() as conn:
            cursor = await conn.execute("DELETE FROM tablero_opinion WHERE id = ?", (opinion_id,))
            await conn.commit()
        return cursor.rowcount > 0
