import aiosqlite
import json
from uuid import UUID
from typing import List, Optional
from datetime import datetime
from src.domain.models import Story, ActInput, GeneratedAct, NarrativeState, StoryStatus
from src.domain.interfaces import StoryRepository

class SQLiteStoryRepository:
    """Implementación de persistencia en SQLite usando aiosqlite."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def initialize(self):
        """Crea las tablas si no existen."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stories (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    protagonistas TEXT,
                    relator TEXT,
                    escenarios TEXT,
                    sinopsis TEXT,
                    atmosfera TEXT,
                    status TEXT,
                    created_at TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS reglas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    story_id TEXT,
                    content TEXT,
                    FOREIGN KEY(story_id) REFERENCES stories(id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS actos_input (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    story_id TEXT,
                    number INTEGER,
                    title TEXT,
                    mission TEXT,
                    FOREIGN KEY(story_id) REFERENCES stories(id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS generated_acts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    story_id TEXT,
                    number INTEGER,
                    content TEXT,
                    raw_output TEXT,
                    word_count INTEGER,
                    created_at TIMESTAMP,
                    FOREIGN KEY(story_id) REFERENCES stories(id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS narrative_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    act_id INTEGER,
                    location TEXT,
                    characters TEXT,
                    situation TEXT,
                    active_threat TEXT,
                    goal TEXT,
                    last_action TEXT,
                    FOREIGN KEY(act_id) REFERENCES generated_acts(id)
                )
            """)
            await db.commit()

    async def save_story(self, story: Story) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO stories (id, title, protagonistas, relator, escenarios, sinopsis, atmosfera, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (str(story.id), story.title, story.protagonistas, story.relator, story.escenarios, story.sinopsis, story.atmosfera, story.status.value, story.created_at)
            )
            for regla in story.reglas:
                await db.execute("INSERT INTO reglas (story_id, content) VALUES (?, ?)", (str(story.id), regla))
            
            for acto in story.actos_input:
                await db.execute("INSERT INTO actos_input (story_id, number, title, mission) VALUES (?, ?, ?, ?)", 
                                 (str(story.id), acto.number, acto.title, acto.mission))
            await db.commit()

    async def get_story(self, story_id: UUID) -> Optional[Story]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM stories WHERE id = ?", (str(story_id),)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                
                # Cargar reglas
                reglas = []
                async with db.execute("SELECT content FROM reglas WHERE story_id = ?", (str(story_id),)) as c:
                    reglas = [r[0] for r in await c.fetchall()]
                
                # Cargar actos_input
                actos_input = []
                async with db.execute("SELECT number, title, mission FROM actos_input WHERE story_id = ? ORDER BY number", (str(story_id),)) as c:
                    for r in await c.fetchall():
                        actos_input.append(ActInput(number=r[0], title=r[1], mission=r[2]))
                
                return Story(
                    id=UUID(row['id']),
                    title=row['title'],
                    protagonistas=row['protagonistas'],
                    relator=row['relator'],
                    escenarios=row['escenarios'],
                    sinopsis=row['sinopsis'],
                    atmosfera=row['atmosfera'],
                    status=StoryStatus(row['status']),
                    created_at=datetime.fromisoformat(row['created_at']) if isinstance(row['created_at'], str) else row['created_at'],
                    reglas=reglas,
                    actos_input=actos_input
                )

    async def save_act(self, story_id: UUID, act: GeneratedAct) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO generated_acts (story_id, number, content, raw_output, word_count, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (str(story_id), act.number, act.content, act.raw_output, act.word_count, act.created_at)
            )
            act_id = cursor.lastrowid
            
            if act.state_after:
                s = act.state_after
                await db.execute(
                    "INSERT INTO narrative_states (act_id, location, characters, situation, active_threat, goal, last_action) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (act_id, s.location, s.characters, s.situation, s.active_threat, s.goal, s.last_action)
                )
            await db.commit()
