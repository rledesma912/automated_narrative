"""Registro de las llamadas a la IA (Spec-740 Parte B)."""

from uuid import UUID

from src.domain.llm_context import LLMCall
from src.infrastructure.database.connection import get_connection
from src.utils.timezone import now_argentina

_COLUMNS = (
    "story_id, job_id, narrative_id, profile, role, act, provider, model, via, "
    "fallback_attempts, fallback_trail, respaldo, input_tokens, output_tokens, elapsed_s, "
    "created_at"
)


def _row_to_call(row) -> LLMCall:
    return LLMCall(
        story_id=UUID(row["story_id"]),
        job_id=UUID(row["job_id"]),
        narrative_id=UUID(row["narrative_id"]) if row["narrative_id"] else None,
        profile=row["profile"],
        role=row["role"],
        act=row["act"],
        provider=row["provider"],
        model=row["model"],
        via=row["via"],
        fallback_attempts=row["fallback_attempts"] or 0,
        fallback_trail=row["fallback_trail"],
        respaldo=bool(row["respaldo"]),
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        elapsed_s=row["elapsed_s"],
        created_at=row["created_at"],
    )


class SQLLLMCallRepository:
    async def add(self, call: LLMCall) -> None:
        conn = await get_connection()
        try:
            await conn.execute(
                f"INSERT INTO llm_call ({_COLUMNS}) VALUES ({', '.join('?' * 16)})",
                (
                    str(call.story_id),
                    str(call.job_id),
                    str(call.narrative_id) if call.narrative_id else None,
                    call.profile,
                    call.role,
                    call.act,
                    call.provider,
                    call.model,
                    call.via,
                    call.fallback_attempts,
                    call.fallback_trail,
                    int(call.respaldo),
                    call.input_tokens,
                    call.output_tokens,
                    call.elapsed_s,
                    call.created_at or now_argentina().isoformat(),
                ),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def link_narrative(self, job_id: UUID, narrative_id: UUID) -> None:
        """Las llamadas del job quedan con el relato que escribió (o regeneró)."""
        conn = await get_connection()
        try:
            await conn.execute(
                "UPDATE llm_call SET narrative_id = ? WHERE job_id = ?",
                (str(narrative_id), str(job_id)),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def for_narrative(self, narrative_id: UUID) -> list[LLMCall]:
        """Las llamadas de los jobs que escribieron o regeneraron este relato, en orden."""
        return await self._select("narrative_id = ?", (str(narrative_id),))

    async def for_story(self, story_id: UUID) -> list[LLMCall]:
        return await self._select("story_id = ?", (str(story_id),))

    async def _select(self, where: str, args: tuple) -> list[LLMCall]:
        conn = await get_connection()
        try:
            cursor = await conn.execute(
                f"SELECT {_COLUMNS} FROM llm_call WHERE {where} ORDER BY created_at, id", args
            )
            return [_row_to_call(r) for r in await cursor.fetchall()]
        finally:
            await conn.close()
