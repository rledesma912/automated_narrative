import pytest
import os
from uuid import uuid4
from src.infrastructure.database.repository import SQLiteStoryRepository
from src.domain.models import Story, ActInput, GeneratedAct, NarrativeState

@pytest.fixture
async def repo():
    """Fixture que provee un repositorio con base de datos limpia para cada test."""
    db_path = "test_stories.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    repository = SQLiteStoryRepository(db_path)
    await repository.initialize()
    yield repository
    
    # Limpieza después del test
    if os.path.exists(db_path):
        os.remove(db_path)

@pytest.mark.asyncio
async def test_save_and_get_story(repo):
    """Valida el ciclo completo de guardado y recuperación de una historia."""
    story = Story(
        id=uuid4(),
        title="Test Integration Story",
        protagonistas="Protagonista 1",
        relator="Relator X",
        escenarios="Escenario A",
        sinopsis="Una sinopsis de prueba.",
        atmosfera="Misterio",
        reglas=["Regla 1", "Regla 2"],
        actos_input=[
            ActInput(number=1, title="Acto 1", mission="Misión 1"),
            ActInput(number=2, title="Acto 2", mission="Misión 2")
        ]
    )
    
    await repo.save_story(story)
    retrieved = await repo.get_story(story.id)
    
    assert retrieved is not None
    assert retrieved.id == story.id
    assert retrieved.title == story.title
    assert len(retrieved.reglas) == 2
    assert len(retrieved.actos_input) == 2

@pytest.mark.asyncio
async def test_save_act_with_state(repo):
    """Valida que se guarden correctamente los actos generados y sus estados narrativos."""
    story_id = uuid4()
    
    act = GeneratedAct(
        number=1,
        content="Contenido del capítulo...",
        raw_output="Raw output...",
        word_count=100,
        state_after=NarrativeState(
            location="El Bosque",
            characters="Marcos",
            situation="Perdido",
            active_threat="Lobo",
            goal="Escapar",
            last_action="Correr"
        )
    )
    
    # No fallar al insertar
    await repo.save_act(story_id, act)
    
    # Validar que existe en la DB manualmente
    import aiosqlite
    async with aiosqlite.connect("test_stories.db") as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM generated_acts WHERE story_id = ?", (str(story_id),)) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row['number'] == 1
            act_id = row['id']
            
        async with db.execute("SELECT * FROM narrative_states WHERE act_id = ?", (act_id,)) as cursor:
            state_row = await cursor.fetchone()
            assert state_row is not None
            assert state_row['location'] == "El Bosque"
            assert state_row['active_threat'] == "Lobo"
