"""Spec-740 S2 (Parte D): un perfil por largo, y el largo deshabilitado con `off`.

`LLM_PROFILE_<MEDIO>` (p. ej. `LLM_PROFILE_MEDIO`): vacío = el de siempre; `off` = ese
largo no se escribe; el nombre de un perfil = ese perfil, solo para los jobs de sus
historias. Sin llamadas reales: el mock y dobles.
"""

import asyncio
import copy
import uuid
from pathlib import Path

import httpx
import pytest
import yaml

import src.config as config
from src.config import settings
from src.main import app

CORE = yaml.safe_load(
    (Path(__file__).parents[2] / "config" / "llm_core_definitions.yaml").read_text("utf-8")
)
CORTO = "freellmapi-libre"
MEDIO = "hibrido-sonnet55"


@pytest.fixture
def perfiles(monkeypatch):
    """El de siempre (corto) es FreeLLMAPI; el largo, el híbrido con Claude."""
    monkeypatch.setattr(config, "_profile", copy.deepcopy(CORE["profiles"][CORTO]))
    monkeypatch.setattr(config, "_active_profile_name", CORTO)
    monkeypatch.setattr(config, "_llm_core", CORE)
    monkeypatch.setattr(settings, "freellmapi_api_key", "clave-de-prueba")
    monkeypatch.setattr(settings, "anthropic_api_key", "clave-de-prueba")

    monkeypatch.delenv("LLM_PROFILE_LARGO", raising=False)  # Spec-750: solo se prueba la media

    def largo(value: str | None):
        if value is None:
            monkeypatch.delenv("LLM_PROFILE_MEDIO", raising=False)
        else:
            monkeypatch.setenv("LLM_PROFILE_MEDIO", value)

    return largo


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── Resolución ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("value", [None, "", "  "])
def test_sin_variable_el_largo_usa_el_de_siempre(perfiles, value):
    perfiles(value)
    assert settings.profile_for("medio") == CORTO
    assert settings.profile_for("corto") == CORTO
    assert settings.structure_enabled("medio")


@pytest.mark.parametrize("value", ["off", "OFF", " off "])
def test_off_deshabilita_ese_largo(perfiles, value):
    perfiles(value)
    assert settings.profile_for("medio") is None
    assert not settings.structure_enabled("medio")
    assert settings.structure_enabled("corto")


def test_otro_perfil_solo_para_ese_largo(perfiles):
    perfiles(MEDIO)
    assert settings.profile_for("medio") == MEDIO
    assert settings.profile_for("corto") == CORTO


def test_un_perfil_que_no_existe_no_arranca(perfiles):
    perfiles("no-existe")
    with pytest.raises(ValueError, match="LLM_PROFILE_MEDIO"):
        config.check_structure_profiles()


def test_off_y_vacio_y_perfiles_validos_arrancan(perfiles):
    for value in (None, "", "off", MEDIO):
        perfiles(value)
        config.check_structure_profiles()


# ── El perfil en el contexto ───────────────────────────────────────────────


async def test_cada_tarea_lee_la_config_de_su_perfil(perfiles):
    perfiles(MEDIO)
    listos = asyncio.Barrier(2)

    async def job(profile: str):
        config.use_profile(profile)
        await listos.wait()
        return (
            settings.active_profile_name,
            settings.role_provider("voz"),
            settings.role_config("voz")["model"],
        )

    corto, largo = await asyncio.gather(
        asyncio.create_task(job(CORTO)), asyncio.create_task(job(MEDIO))
    )
    assert corto == (CORTO, "freellmapi", "auto:narrativa")
    assert largo == (MEDIO, "anthropic", "claude-sonnet-5-5")


async def test_fuera_de_un_job_manda_el_de_siempre(perfiles):
    perfiles(MEDIO)

    async def tarea():
        return settings.active_profile_name

    assert await asyncio.create_task(tarea()) == CORTO


async def test_el_tope_de_espera_y_los_tiempos_son_del_perfil(perfiles):
    perfiles(MEDIO)

    async def job(profile: str):
        config.use_profile(profile)
        return settings.active_profile_config().get("freellmapi"), settings.estimated_seconds(
            "full_generation"
        )

    corto = await asyncio.create_task(job(CORTO))
    largo = await asyncio.create_task(job(MEDIO))
    assert corto[0] == {"max_espera_s": 120}
    assert largo[0] is None
    assert corto[1] != largo[1]


async def test_la_factory_arma_el_adapter_del_perfil_del_job(perfiles):
    from src.infrastructure.adapters import AnthropicAdapter, FreeLLMAPIAdapter
    from src.infrastructure.factories import LLMFactory

    perfiles(MEDIO)

    async def job(profile: str):
        config.use_profile(profile)
        return LLMFactory.get_provider().inner

    corto = await asyncio.create_task(job(CORTO))
    largo = await asyncio.create_task(job(MEDIO))
    assert isinstance(corto, FreeLLMAPIAdapter)
    assert isinstance(largo.adapter_for("voz"), AnthropicAdapter)


# ── JobManager ─────────────────────────────────────────────────────────────


class _Story:
    def __init__(self, structure: str):
        self.id = uuid.uuid4()
        self.title = "Una historia"
        self.structure = structure
        self.outline = []


class _Jobs:
    def __init__(self):
        self.created = []

    async def get_active_for_story(self, story_id):
        return None

    async def create(self, job):
        self.created.append(job)

    async def mark_running(self, job_id):
        return None

    async def update_progress(self, *args, **kwargs):
        return None

    async def finish(self, *args, **kwargs):
        return None


class _Estimator:
    async def estimate(self, kind, profile, structure):
        from src.application.services.job_duration_estimator import Estimate

        return Estimate(seconds=10, source="default", samples=0)


def _manager(jobs):
    from src.application.services.event_bus import EventBus
    from src.application.services.job_manager import JobManager

    return JobManager(EventBus(), jobs, story_repo=None, estimator=_Estimator())


async def test_el_job_corre_con_el_perfil_de_su_historia(perfiles):
    from src.domain.jobs import JobKind
    from src.domain.streaming import StreamEvent, StreamEventType

    perfiles(MEDIO)
    jobs = _Jobs()
    manager = _manager(jobs)
    seen = {}

    def runner(name):
        def _run():
            async def gen():
                seen[name] = settings.active_profile_name
                yield StreamEvent(event=StreamEventType.DONE, data={})

            return gen()

        return _run

    for name, structure in (("corto", "corto"), ("medio", "medio")):
        job = await manager.submit(_Story(structure), JobKind.CONSULT, runner(name))
        await manager.wait(job.id)

    assert seen == {"corto": CORTO, "medio": MEDIO}
    assert [j.params["profile"] for j in jobs.created] == [CORTO, MEDIO]


@pytest.mark.parametrize("kind", ["full_generation", "regenerate_voz", "consult", "video_script"])
async def test_con_el_largo_off_ningun_job_arranca(perfiles, kind):
    from src.application.services.job_manager import StructureDisabledError
    from src.domain.jobs import JobKind

    perfiles("off")
    jobs = _Jobs()
    with pytest.raises(StructureDisabledError):
        await _manager(jobs).submit(_Story("medio"), JobKind(kind), lambda: None)
    assert jobs.created == []


# ── API ────────────────────────────────────────────────────────────────────


async def test_options_dice_que_largo_esta_disponible(perfiles, client):
    from src.messages import message

    perfiles("off")
    structures = (await client.get("/api/v1/authoring/options")).json()["structures"]
    by_id = {s["id"]: s for s in structures}

    assert by_id["corto"]["disponible"] is True
    assert by_id["corto"].get("nota") is None
    assert by_id["medio"]["disponible"] is False
    assert by_id["medio"]["nota"] == message("job.medio_deshabilitado")


async def test_options_con_todo_disponible(perfiles, client):
    perfiles(None)
    structures = (await client.get("/api/v1/authoring/options")).json()["structures"]
    assert all(s["disponible"] for s in structures)


async def test_health_y_perfil_activo_muestran_los_dos(perfiles, client, monkeypatch):
    perfiles(MEDIO)
    real = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **k: real(
            *a, transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={})), **k
        ),
    )

    health = (await client.get("/api/v1/health")).json()
    assert set(health["checks"]["providers"]) == {"freellmapi", "anthropic", "ollama"}
    assert health["profiles"] == {"corto": CORTO, "medio": MEDIO, "largo": CORTO}

    active = (await client.get("/api/v1/config/active-profile")).json()
    assert active["active_profile"] == CORTO
    assert active["profiles"] == {"corto": CORTO, "medio": MEDIO, "largo": CORTO}


async def test_health_con_el_largo_off(perfiles, client):
    perfiles("off")
    health = (await client.get("/api/v1/health")).json()
    assert health["profiles"]["medio"] is None


# ── Crear, cambiar de largo y lanzar con el largo `off` ────────────────────

API = "/api/v1/authoring"
FORM = {
    "title": "La pena del colectivo",
    "genero": "",
    "subgenero": "",
    "premise": "José ve por el espejo a una mujer que murió en su micro.",
    "effect": "pavor",
    "telling": "caso",
    "protagonist_name": "José",
    "protagonist_role": "Chofer de micros",
    "narrator": "",
}


@pytest.fixture
async def api(perfiles, monkeypatch, tmp_path):  # noqa: ARG001 — el orden de las fixtures
    from src.infrastructure.adapters import MockLLMAdapter
    from src.infrastructure.database.connection import init_db
    from src.infrastructure.factories import LLMFactory

    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'a.db'}")
    monkeypatch.setattr(
        LLMFactory, "get_provider", staticmethod(lambda *_a, **_k: MockLLMAdapter())
    )
    await init_db()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def _create(api, structure: str) -> dict:
    resp = await api.post(f"{API}/stories", json={**FORM, "structure": structure})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_crear_un_largo_con_off_es_422(perfiles, api):
    from src.messages import message

    perfiles("off")
    resp = await api.post(f"{API}/stories", json={**FORM, "structure": "medio"})
    assert resp.status_code == 422
    assert resp.json()["detail"] == message("job.medio_deshabilitado")
    await _create(api, "corto")  # el corto, igual que siempre


async def test_pasar_a_largo_con_off_es_422_y_a_corto_se_puede(perfiles, api):
    perfiles(None)
    largo = await _create(api, "medio")
    corto = await _create(api, "corto")

    perfiles("off")
    resp = await api.put(
        f"{API}/stories/{corto['story_id']}/structure", json={"structure": "medio"}
    )
    assert resp.status_code == 422
    # La salida de una historia larga: pasarla a corto (C6).
    resp = await api.put(
        f"{API}/stories/{largo['story_id']}/structure", json={"structure": "corto"}
    )
    assert resp.status_code == 200
    assert resp.json()["structure"] == "corto"


async def test_lanzar_ia_sobre_un_largo_con_off_es_409(perfiles, api):
    from src.messages import message

    perfiles(None)
    largo = await _create(api, "medio")

    perfiles("off")
    resp = await api.post(f"/api/v1/stories/{largo['story_id']}/jobs", json={"kind": "consult"})
    assert resp.status_code == 409
    assert resp.json()["detail"] == message("job.medio_deshabilitado")
    assert "X-Job-Id" not in resp.headers  # no hay un job en curso: es el largo


async def test_el_largo_off_va_antes_que_las_validaciones(perfiles, api):
    """Una historia larga sin «¿De qué trata?» dice que el largo no se escribe (no el 422)."""
    from src.infrastructure.database.repositories import SQLStoryRepository
    from src.messages import message

    perfiles(None)
    largo = await _create(api, "medio")
    story = await SQLStoryRepository().get_by_id(uuid.UUID(largo["story_id"]))
    await SQLStoryRepository().update_direction(
        story.id, story.direction.model_copy(update={"premise": ""})
    )

    perfiles("off")
    resp = await api.post(f"/api/v1/stories/{largo['story_id']}/jobs", json={"kind": "consult"})
    assert resp.status_code == 409
    assert resp.json()["detail"] == message("job.medio_deshabilitado")


async def test_el_estado_y_la_historia_dicen_si_hay_ia(perfiles, api):
    from src.messages import message

    perfiles(None)
    largo = await _create(api, "medio")
    corto = await _create(api, "corto")
    assert largo["ia_disponible"] is True

    perfiles("off")
    state = (await api.get(f"{API}/stories/{largo['story_id']}")).json()
    assert (state["ia_disponible"], state["ia_nota"]) == (False, message("job.medio_deshabilitado"))
    story = (await api.get(f"/api/v1/stories/{largo['story_id']}")).json()
    assert (story["ia_disponible"], story["ia_nota"]) == (False, message("job.medio_deshabilitado"))
    assert (await api.get(f"/api/v1/stories/{corto['story_id']}")).json()["ia_disponible"] is True
