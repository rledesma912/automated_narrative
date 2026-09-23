"""SQL Job Repository (Spec-460)."""

import json
import logging
from datetime import datetime
from uuid import UUID

from src.domain.jobs import (
    ACTIVE_JOB_STATUSES,
    INTERRUPTED_ERROR,
    Job,
    JobStage,
    JobStatus,
)
from src.infrastructure.database.connection import get_connection
from src.utils.timezone import now_argentina

logger = logging.getLogger(__name__)

_ACTIVE = tuple(s.value for s in ACTIVE_JOB_STATUSES)
_ACTIVE_SQL = f"status IN ({', '.join('?' for _ in _ACTIVE)})"


class SQLJobRepository:
    """SQLite implementation of the generation_job repository."""

    async def create(self, job: Job) -> Job:
        """Persiste un job nuevo.

        Raises:
            sqlite3.IntegrityError: si la historia ya tiene un job activo
                (índice único parcial `uq_generation_job_active_story`).
        """
        conn = await get_connection()
        try:
            await conn.execute(
                """INSERT INTO generation_job
                (id, story_id, kind, status, stage, beat, total_beats, params,
                 error, narrative_id, created_at, started_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(job.id),
                    str(job.story_id),
                    job.kind.value,
                    job.status.value,
                    job.stage.value if job.stage else None,
                    job.beat,
                    job.total_beats,
                    json.dumps(job.params, ensure_ascii=False),
                    job.error,
                    str(job.narrative_id) if job.narrative_id else None,
                    job.created_at.isoformat(),
                    job.started_at.isoformat() if job.started_at else None,
                    job.finished_at.isoformat() if job.finished_at else None,
                ),
            )
            await conn.commit()
        finally:
            await conn.close()
        return job

    async def mark_running(self, job_id: UUID) -> None:
        await self._update(
            job_id, status=JobStatus.RUNNING.value, started_at=now_argentina().isoformat()
        )

    async def update_progress(
        self, job_id: UUID, stage: JobStage, beat: int | None, total_beats: int | None = None
    ) -> None:
        fields = {"stage": stage.value, "beat": beat}
        if total_beats is not None:
            fields["total_beats"] = total_beats
        await self._update(job_id, **fields)

    async def finish(
        self,
        job_id: UUID,
        status: JobStatus,
        error: str | None = None,
        narrative_id: UUID | str | None = None,
    ) -> None:
        await self._update(
            job_id,
            status=status.value,
            error=error,
            narrative_id=str(narrative_id) if narrative_id else None,
            finished_at=now_argentina().isoformat(),
        )

    async def get(self, job_id: UUID) -> Job | None:
        rows = await self._select("id = ?", (str(job_id),))
        return rows[0] if rows else None

    async def get_active_for_story(self, story_id: UUID) -> Job | None:
        rows = await self._select(f"story_id = ? AND {_ACTIVE_SQL}", (str(story_id), *_ACTIVE))
        return rows[0] if rows else None

    async def list_active(self) -> list[Job]:
        return await self._select(_ACTIVE_SQL, _ACTIVE, order="created_at ASC")

    async def list_recent(self, since: datetime) -> list[Job]:
        """Jobs terminados desde `since` (para el `snapshot` del canal global)."""
        return await self._select(
            f"NOT {_ACTIVE_SQL} AND finished_at >= ?", (*_ACTIVE, since.isoformat())
        )

    async def recover_interrupted(self) -> int:
        """Marca `failed` los jobs que quedaron activos (el proceso murió con ellos)."""
        conn = await get_connection()
        try:
            cursor = await conn.execute(
                f"UPDATE generation_job SET status = ?, error = ?, finished_at = ? "
                f"WHERE {_ACTIVE_SQL}",
                (JobStatus.FAILED.value, INTERRUPTED_ERROR, now_argentina().isoformat(), *_ACTIVE),
            )
            count = cursor.rowcount
            await conn.commit()
        finally:
            await conn.close()
        if count > 0:
            logger.warning("Recuperados %d jobs interrumpidos tras reinicio", count)
        return count

    async def _update(self, job_id: UUID, **fields) -> None:
        assignments = ", ".join(f"{name} = ?" for name in fields)
        conn = await get_connection()
        try:
            await conn.execute(
                f"UPDATE generation_job SET {assignments} WHERE id = ?",
                (*fields.values(), str(job_id)),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def _select(self, where: str, params: tuple, order: str = "created_at DESC") -> list[Job]:
        conn = await get_connection()
        try:
            cursor = await conn.execute(
                f"SELECT * FROM generation_job WHERE {where} ORDER BY {order}", params
            )
            rows = await cursor.fetchall()
        finally:
            await conn.close()
        return [self._to_job(row) for row in rows]

    @staticmethod
    def _to_job(row) -> Job:
        def _dt(value: str | None) -> datetime | None:
            return datetime.fromisoformat(value) if value else None

        return Job(
            id=UUID(row["id"]),
            story_id=UUID(row["story_id"]),
            kind=row["kind"],
            status=row["status"],
            stage=row["stage"],
            beat=row["beat"],
            total_beats=row["total_beats"],
            params=json.loads(row["params"] or "{}"),
            error=row["error"],
            narrative_id=UUID(row["narrative_id"]) if row["narrative_id"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=_dt(row["started_at"]),
            finished_at=_dt(row["finished_at"]),
        )
