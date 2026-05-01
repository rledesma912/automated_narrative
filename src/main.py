"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repositories.story_repository import SQLStoryRepository
from src.presentation.routers import beat_router, export_router, story_router, stream_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await SQLStoryRepository().recover_processing_stories()
    yield


app = FastAPI(
    title="NarrativeForge API",
    version="1.0.0",
    description="Sistema de generación granular de relatos de terror",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(story_router, prefix="/api/v1")
app.include_router(beat_router, prefix="/api/v1")
app.include_router(export_router, prefix="/api/v1")
app.include_router(stream_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"status": "ok", "service": "NarrativeForge"}
