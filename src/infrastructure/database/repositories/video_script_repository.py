"""SQL repository del paquete para el video (Spec-610)."""

import json
import logging
from datetime import datetime
from uuid import UUID

from src.domain.video import VideoScript
from src.infrastructure.database.connection import connection
from src.utils.timezone import now_argentina

logger = logging.getLogger(__name__)


class SQLVideoScriptRepository:
    """Un paquete por variante (`narrative_id` único); se borra con la variante."""

    async def get_by_narrative(self, narrative_id: UUID) -> VideoScript | None:
        async with connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM video_script WHERE narrative_id = ?", (str(narrative_id),)
            )
            row = await cursor.fetchone()
        return self._to_entity(row) if row else None

    async def save(self, script: VideoScript) -> VideoScript:
        """Guarda el paquete; si la variante ya tenía uno, lo reemplaza."""
        script.updated_at = now_argentina()
        async with connection() as conn:
            await conn.execute(
                "DELETE FROM video_script WHERE narrative_id = ? AND id != ?",
                (str(script.narrative_id), str(script.id)),
            )
            await conn.execute(
                """INSERT OR REPLACE INTO video_script
                (id, narrative_id, data, parrafos_por_acto, narrative_hash, seed,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(script.id),
                    str(script.narrative_id),
                    json.dumps(script.data(), ensure_ascii=False),
                    json.dumps(script.parrafos_por_acto),
                    script.narrative_hash,
                    script.seed,
                    script.created_at.isoformat(),
                    script.updated_at.isoformat(),
                ),
            )
            await conn.commit()
        logger.debug(f"[VIDEO_SCRIPT] Guardado {script.id} (variante {script.narrative_id})")
        return script

    @staticmethod
    def _to_entity(row) -> VideoScript:
        return VideoScript(
            id=row["id"],
            narrative_id=row["narrative_id"],
            **json.loads(row["data"]),
            parrafos_por_acto={int(k): v for k, v in json.loads(row["parrafos_por_acto"]).items()},
            narrative_hash=row["narrative_hash"],
            seed=row["seed"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
