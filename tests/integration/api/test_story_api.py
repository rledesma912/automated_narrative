import pytest
import os
from fastapi.testclient import TestClient
from src.main import app
from src.config import settings

client = TestClient(app)

@pytest.fixture
def clean_db():
    db_path = "test_api_stories.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Overwrite settings for test
    # settings.database_url = f"sqlite+aiosqlite:///{db_path}"
    
    yield db_path
    
    if os.path.exists(db_path):
        os.remove(db_path)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "NarrativeForge API"

def test_start_generation_success():
    """Valida que el endpoint /generate cree una historia correctamente."""
    payload = {
        "title": "El Regreso",
        "protagonistas": "Pedro y Ana",
        "relator": "Pedro",
        "escenarios": "Cabaña",
        "sinopsis": "Vuelven a la cabaña después de años.",
        "atmosfera": "Suspenso",
        "reglas": ["Regla 1"],
        "actos_input": [
            {"number": 1, "title": "Llegada", "mission": "Entrar a la cabaña"}
        ]
    }
    
    response = client.post("/api/v1/generate", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "El Regreso"
    assert "id" in data
