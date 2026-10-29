"""Jobs del asistente de autoría (Spec-530 S3): taller, escaleta y revisión.

Corren en el JobManager como la generación: sobreviven a cerrar la pestaña, un
solo job activo por historia, eventos por el bus y tiempo estimado (Spec-510).
Cada runner relee la historia al arrancar (lo guardado manda) y persiste su
resultado antes de publicar `done`.
"""

import logging
from uuid import UUID

from src.application.services.authoring import (
    context,
    elenco,
    final_de_la_idea,
    form_suggester,
    revisor,
)
from src.application.services.authoring.consultant import WorkshopConsultant
from src.application.services.authoring.planner import OutlinePlanner
from src.application.services.authoring.verifier import OutlineVerifier
from src.application.services.job_manager import JobRunner
from src.application.services.streaming_service import stage_event
from src.domain.exceptions import (
    LLMResponseError,
    LLMStructuredOutputError,
    LLMUnavailableError,
)
from src.domain.jobs import Job, JobKind, JobStage
from src.domain.models import Story
from src.domain.streaming import StreamEvent, StreamEventType
from src.infrastructure.database.repositories import SQLStoryRepository
from src.infrastructure.factories import LLMFactory
from src.presentation.runtime import job_manager

logger = logging.getLogger(__name__)


def _done(story_id: UUID, **data) -> StreamEvent:
    return StreamEvent(event=StreamEventType.DONE, data={"story_id": str(story_id), **data})


async def _load(story_id: UUID) -> Story:
    story = await SQLStoryRepository().get_by_id(story_id)
    if story is None:
        raise ValueError(f"Historia no encontrada: {story_id}")
    return story


async def _with_ending(story: Story, llm) -> Story:
    """Spec-690: si la idea cuenta cómo termina, el final queda resuelto en «Preguntas»."""
    item = await final_de_la_idea.FinalDeLaIdea(llm).ensure(story)
    if item is not None:
        await SQLStoryRepository().save_workshop_items(story.id, [item])
    return final_de_la_idea.apply(story, item)


async def _idea_leida(story: Story, paso: str) -> None:
    """Spec-700 D12: la idea que leyó la IA queda sellada en ese paso (al terminar bien).
    Con la historia del arranque del job: mientras corre, «Tu idea» no se puede guardar."""
    if story.direction is not None:
        story = context.con_idea_leida(story, paso)
        await SQLStoryRepository().update_direction(story.id, story.direction)


async def _with_cast(story: Story, acts) -> Story:
    """Spec-700 D22: los personajes que nombró la autora se suman solos antes de revisar
    (así la regla de los personajes no pregunta por ellos)."""
    names = elenco.personajes_de_la_autora(story, acts)
    if not names:
        return story
    story = elenco.con_personajes(story, names)
    await SQLStoryRepository().update_inputs(story)
    return story


async def _revisar(story: Story, llm) -> Story:
    """Spec-700 A3: la idea cambió; antes de preguntar, qué respuestas ya no van. Sin el rol
    o si la IA no responde, la ronda sigue y queda qué cambió para mostrarlo (D26)."""
    if revisor.con_ia():
        try:
            marked = await revisor.RevisorDeRespuestas(llm).revisar(story)
        except (LLMUnavailableError, LLMResponseError, LLMStructuredOutputError) as e:
            logger.warning("[REVISOR] sin revisión, queda la nota: %s", e)
        else:
            if marked:
                await SQLStoryRepository().save_workshop_items(story.id, marked)
            return revisor.apply(story, marked)
    pending = revisor.sin_revisar(story)
    if pending is not story:
        await SQLStoryRepository().update_direction(story.id, pending.direction)
    return pending


def consult_runner(story_id: UUID) -> JobRunner:
    def _run():
        async def _gen():
            yield stage_event(JobStage.CONSULTOR, None, None)
            llm = LLMFactory.get_provider()
            story = await _with_ending(await _load(story_id), llm)  # Spec-690
            if context.idea_cambio(story)["preguntas"]:
                story = await _revisar(story, llm)  # Spec-700 A3
            result = await WorkshopConsultant(llm).analyze(story)
            await SQLStoryRepository().save_workshop_items(story_id, result.items)
            await _idea_leida(story, "preguntas")  # Spec-700 D12
            yield _done(story_id, finish={"kind": result.finish.kind, "text": result.finish.text})

        return _gen()

    return _run


def plan_outline_runner(story_id: UUID) -> JobRunner:
    def _run():
        async def _gen():
            llm = LLMFactory.get_provider()
            yield stage_event(JobStage.PLANIFICADOR, None, None)
            story = await _with_ending(await _load(story_id), llm)  # Spec-690 D3
            acts, _ = await OutlinePlanner(llm).plan(story)
            story = await _with_cast(story, acts)
            yield stage_event(JobStage.VERIFICADOR, None, None)
            checked = await OutlineVerifier(llm).verify(story, acts)
            await SQLStoryRepository().save_outline(story_id, checked.outline)
            await _idea_leida(story, "actos")  # Spec-700 D12
            yield _done(story_id, missing_decisions=checked.missing_decisions)

        return _gen()

    return _run


def verify_outline_runner(story_id: UUID) -> JobRunner:
    def _run():
        async def _gen():
            yield stage_event(JobStage.VERIFICADOR, None, None)
            story = await _load(story_id)
            story = await _with_cast(story, story.outline)
            checked = await OutlineVerifier(LLMFactory.get_provider()).verify(story, story.outline)
            await SQLStoryRepository().save_outline(story_id, checked.outline)
            yield _done(story_id, missing_decisions=checked.missing_decisions)

        return _gen()

    return _run


def suggest_form_runner(story_id: UUID) -> JobRunner:
    """Spec-670 D1: la IA sugiere la clase de historia; se guarda en la dirección."""

    def _run():
        async def _gen():
            yield stage_event(JobStage.CONSULTOR, None, None)
            story = await _load(story_id)
            suggestion, _ = await form_suggester.FormSuggester(LLMFactory.get_provider()).suggest(
                story
            )
            direction = form_suggester.apply(story.direction, suggestion)
            await SQLStoryRepository().update_direction(story_id, direction)
            yield _done(story_id, form=suggestion.form, reason=suggestion.reason)

        return _gen()

    return _run


_RUNNERS = {
    JobKind.CONSULT: consult_runner,
    JobKind.SUGGEST_FORM: suggest_form_runner,
    JobKind.PLAN_OUTLINE: plan_outline_runner,
    JobKind.VERIFY_OUTLINE: verify_outline_runner,
}
AUTHORING_KINDS = tuple(_RUNNERS)


async def submit_authoring(story: Story, kind: JobKind) -> Job:
    """Lanza un job del asistente. Raises JobAlreadyActiveError."""
    return await job_manager.submit(story, kind, _RUNNERS[kind](story.id))
