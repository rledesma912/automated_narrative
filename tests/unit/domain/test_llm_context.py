"""El contexto de una llamada al LLM (Spec-740 T1.2)."""

import asyncio
import uuid

from src.domain import llm_context


async def test_fuera_de_un_job_no_hay_contexto():
    async def tarea():
        return llm_context.current()

    assert await asyncio.create_task(tarea()) is None


async def test_dos_jobs_simultaneos_no_se_pisan():
    ids = {nombre: (uuid.uuid4(), uuid.uuid4()) for nombre in ("a", "b")}
    listos = asyncio.Barrier(2)

    async def job(nombre: str, acto: int):
        llm_context.enter_job(*ids[nombre])
        llm_context.set_act(acto)
        await listos.wait()  # los dos ya fijaron el suyo
        return llm_context.current()

    a, b = await asyncio.gather(asyncio.create_task(job("a", 1)), asyncio.create_task(job("b", 2)))
    assert (a.job_id, a.story_id, a.act) == (*ids["a"], 1)
    assert (b.job_id, b.story_id, b.act) == (*ids["b"], 2)


async def test_una_tarea_hija_hereda_el_contexto():
    job_id, story_id = uuid.uuid4(), uuid.uuid4()

    async def job():
        llm_context.enter_job(job_id, story_id)

        async def hija():
            return llm_context.current()

        return await asyncio.create_task(hija())

    assert (await asyncio.create_task(job())).job_id == job_id


async def test_el_acto_sin_job_no_hace_nada():
    async def tarea():
        llm_context.set_act(3)
        return llm_context.current()

    assert await asyncio.create_task(tarea()) is None
