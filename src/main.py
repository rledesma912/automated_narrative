from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.presentation.api import story_router

app = FastAPI(
    title="NarrativeForge API",
    version="0.1.0",
    description="Motor de generación de relatos de terror con Ollama"
)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En producción se debe restringir a los dominios del wizard
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusión de Routers
app.include_router(story_router.router, prefix="/api/v1", tags=["Stories"])

@app.get("/")
async def root():
    return {"status": "ok", "service": "NarrativeForge API"}
