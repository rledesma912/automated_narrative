"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.presentation.routers import beat_router, export_router, story_router, stream_router

app = FastAPI(
    title="NarrativeForge API",
    version="1.0.0",
    description="Sistema de generación granular de relatos de terror",
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
