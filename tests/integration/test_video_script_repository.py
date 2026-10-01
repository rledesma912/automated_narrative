"""Spec-610 T2.1: el paquete para el video se guarda, se reemplaza y se borra con la variante."""

import uuid

import pytest

from src.config import settings
from src.domain.models import GeneratedNarrative
from src.domain.video import Mark, PresenterLines, ReadingBlock, VideoScript, VisualMoment
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repositories import (
    SQLGeneratedNarrativeRepository,
    SQLStoryRepository,
    SQLVideoScriptRepository,
)


@pytest.fixture
async def narrative(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'v.db'}")
    await init_db()
    from src.domain.models import Story

    story = Story(
        title="No te detengas en el bosque",
        protagonista="Ernesto",
        relator="Primera persona",
        sinopsis="Un camión se queda en el bosque.",
    )
    await SQLStoryRepository().save(story)
    return await SQLGeneratedNarrativeRepository().save(
        GeneratedNarrative(story_template_id=story.id, title="v1", content="## Acto 1\n\nUno.")
    )


def _script(narrative_id, **cambios) -> VideoScript:
    datos = dict(
        narrative_id=narrative_id,
        narra="hombre",
        lector="Lucas",
        bloques=[
            ReadingBlock(
                acto=1,
                desde=1,
                hasta=1,
                indicacion="Tranquilo, como quien confiesa.",
                pausa="corta",
                marcas=[Mark(desde_palabra=0, hasta_palabra=0, texto="Uno.")],
            )
        ],
        momentos=[
            VisualMoment(
                acto=1,
                desde=1,
                hasta=1,
                fuerte=True,
                tipo="animacion",
                que_se_ve="La cabina del camión de noche",
                lugar="cabina",
                prompt_imagen="Night interior of an old truck cab, no people, 16:9",
                prompt_movimiento="Slow push-in.",
                transicion="Fundido desde negro",
                sonido="Motor en marcha",
            )
        ],
        calabaza=PresenterLines(intro="Bienvenidos a mi cripta.", outro="… Buenas noches."),
        parrafos_por_acto={1: 1},
        narrative_hash="abc",
        seed=42,
    )
    datos.update(cambios)
    return VideoScript(**datos)


async def test_guarda_y_lee_igual(narrative):
    repo = SQLVideoScriptRepository()
    guardado = await repo.save(_script(narrative.id))

    leido = await repo.get_by_narrative(narrative.id)

    assert leido.model_dump(exclude={"updated_at"}) == guardado.model_dump(exclude={"updated_at"})
    assert leido.bloques[0].marcas[0].texto == "Uno."
    assert leido.parrafos_por_acto == {1: 1}


async def test_rearmar_reemplaza_el_anterior(narrative):
    repo = SQLVideoScriptRepository()
    await repo.save(_script(narrative.id, seed=1))
    nuevo = await repo.save(_script(narrative.id, seed=2))

    leido = await repo.get_by_narrative(narrative.id)

    assert (leido.id, leido.seed) == (nuevo.id, 2)


@pytest.mark.usefixtures("narrative")
async def test_sin_paquete():
    assert await SQLVideoScriptRepository().get_by_narrative(uuid.uuid4()) is None


async def test_se_borra_con_la_variante(narrative):
    repo = SQLVideoScriptRepository()
    await repo.save(_script(narrative.id))

    await SQLGeneratedNarrativeRepository().delete(narrative.id)

    assert await repo.get_by_narrative(narrative.id) is None


def test_un_rango_invertido_no_vale():
    with pytest.raises(ValueError, match="rango invertido"):
        ReadingBlock(acto=1, desde=3, hasta=2)
