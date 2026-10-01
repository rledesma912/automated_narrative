"""Spec-610 T2.5: el job `video_script` arma el paquete con el mock y se lee por la API."""

import asyncio
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from src.config import settings
from src.domain.models import GeneratedNarrative
from src.infrastructure.adapters import MockLLMAdapter
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repositories import SQLGeneratedNarrativeRepository
from src.infrastructure.factories import LLMFactory
from src.main import app

_PAYLOAD = {
    "title": "No te detengas en el bosque",
    "protagonista": "Ernesto: camionero",
    "relator": "Primera persona en pasado. Narrador: Ernesto.",
    "escenarios": "El bosque: la ruta",
    "sinopsis": "Un camión se queda en el bosque.",
}
CONTENT = "\n\n".join(
    f"## Acto {a}\n\n" + "\n\n".join(f"Párrafo {p} del acto {a}." for p in range(1, 4))
    for a in range(1, 6)
)


@pytest.fixture
async def client(monkeypatch, tmp_path) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'vs.db'}")
    monkeypatch.setattr(
        LLMFactory, "get_provider", staticmethod(lambda *_a, **_k: MockLLMAdapter())
    )
    await init_db()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _narrative(client) -> GeneratedNarrative:
    resp = await client.post("/api/v1/stories?action=save", json=_PAYLOAD)
    assert resp.status_code in (200, 201), resp.text
    return await SQLGeneratedNarrativeRepository().save(
        GeneratedNarrative(
            story_template_id=uuid.UUID(resp.json()["id"]), title="v1", content=CONTENT
        )
    )


async def _wait_job(client, job_id: str) -> dict:
    for _ in range(100):
        job = (await client.get(f"/api/v1/jobs/{job_id}")).json()
        if job["status"] in ("done", "failed"):
            return job
        await asyncio.sleep(0.05)
    raise AssertionError("el job no terminó")


async def test_armar_el_paquete_y_leerlo(client):
    narrative = await _narrative(client)
    url = f"/api/v1/generated-narratives/{narrative.id}/video-script"
    assert (await client.get(url)).status_code == 404

    resp = await client.post(
        f"/api/v1/stories/{narrative.story_template_id}/jobs",
        json={"kind": "video_script", "narrative_id": str(narrative.id)},
    )
    assert resp.status_code == 202, resp.text
    job = await _wait_job(client, resp.json()["job_id"])
    assert job["status"] == "done", job
    assert job["params"]["narrative_id"] == str(narrative.id)

    paquete = (await client.get(url)).json()
    assert paquete["lector"] == "Lucas"
    assert len(paquete["bloques"]) == 15
    assert paquete["parrafos_por_acto"] == {str(n): 3 for n in range(1, 6)}


async def test_sin_relato_o_de_otra_historia(client):
    narrative = await _narrative(client)
    url = f"/api/v1/stories/{narrative.story_template_id}/jobs"
    sin = await client.post(url, json={"kind": "video_script"})
    assert sin.status_code == 422
    otro = await client.post(url, json={"kind": "video_script", "narrative_id": str(uuid.uuid4())})
    assert otro.status_code == 404


# ── T3.1 / T3.2: estado frente al relato y edición ───────────────────────────


async def _armado(client) -> GeneratedNarrative:
    narrative = await _narrative(client)
    resp = await client.post(
        f"/api/v1/stories/{narrative.story_template_id}/jobs",
        json={"kind": "video_script", "narrative_id": str(narrative.id)},
    )
    assert (await _wait_job(client, resp.json()["job_id"]))["status"] == "done"
    return narrative


def _url(narrative, path: str = "") -> str:
    return f"/api/v1/generated-narratives/{narrative.id}/video-script{path}"


async def test_estado_frente_al_relato_corregido(client):
    narrative = await _armado(client)
    assert (await client.get(_url(narrative))).json()["estado"] == {"estado": "al_dia", "actos": []}

    await client.put(
        f"/api/v1/generated-narratives/{narrative.id}/acts/2",
        json={"text": "Párrafo 1 corregido.\n\nPárrafo 2.\n\nPárrafo 3."},
    )
    assert (await client.get(_url(narrative))).json()["estado"]["estado"] == "cambio_el_texto"

    await client.put(
        f"/api/v1/generated-narratives/{narrative.id}/acts/2", json={"text": "Uno solo."}
    )
    body = (await client.get(_url(narrative))).json()
    assert body["estado"] == {"estado": "cambiaron_parrafos", "actos": [2]}
    assert body["lectores"] == ["Yael", "Lucas", "Vale"]
    assert "no people" in body["estilo_imagen"]


async def test_editar_un_bloque_con_marcas(client):
    narrative = await _armado(client)

    resp = await client.put(
        _url(narrative, "/blocks/1"),
        json={"indicacion": "Más lento.", "pausa": "larga", "marcas": [[2, 3], [0, 0]]},
    )

    assert resp.status_code == 200, resp.text
    block = (await client.get(_url(narrative))).json()["bloques"][0]
    assert block["indicacion"] == "Más lento."
    assert block["pausa"] == "larga"
    assert block["marcas"] == [
        {"desde_palabra": 0, "hasta_palabra": 0, "texto": "Párrafo"},
        {"desde_palabra": 2, "hasta_palabra": 3, "texto": "del acto"},
    ]


@pytest.mark.parametrize("marcas", [[[0, 9]], [[1, 0]], [[0, 1], [1, 2]]])
async def test_marcas_invalidas(client, marcas):
    narrative = await _armado(client)
    resp = await client.put(_url(narrative, "/blocks/1"), json={"marcas": marcas})
    assert resp.status_code == 422


async def test_marcas_que_se_pierden_al_corregir(client):
    narrative = await _armado(client)
    await client.put(_url(narrative, "/blocks/1"), json={"marcas": [[2, 3]]})  # «del acto»
    await client.put(
        f"/api/v1/generated-narratives/{narrative.id}/acts/1",
        json={"text": "Otro texto.\n\nPárrafo 2 del acto 1.\n\nPárrafo 3 del acto 1."},
    )
    body = (await client.get(_url(narrative))).json()
    assert body["bloques"][0]["marcas"] == []
    assert body["marcas_perdidas"] == [{"bloque": 1, "texto": "del acto"}]


async def test_editar_momento_lector_y_calabaza(client):
    narrative = await _armado(client)

    m = await client.put(
        _url(narrative, "/moments/2"),
        json={"tipo": "video", "prompt_imagen": " A dark road. ", "transicion": "Corte seco"},
    )
    lector = await client.put(_url(narrative, "/reader"), json={"lector": "Yael"})
    calabaza = await client.put(_url(narrative, "/presenter"), json={"intro": "Hola, cripta."})

    assert m.status_code == lector.status_code == calabaza.status_code == 200
    body = (await client.get(_url(narrative))).json()
    assert body["momentos"][1]["tipo"] == "video"
    assert body["momentos"][1]["prompt_imagen"] == "A dark road."
    assert body["lector"] == "Yael"
    assert body["calabaza"]["intro"] == "Hola, cripta."


async def test_errores_de_edicion(client):
    narrative = await _armado(client)
    assert (await client.put(_url(narrative, "/moments/99"), json={})).status_code == 404
    assert (await client.put(_url(narrative, "/blocks/0"), json={})).status_code == 404
    mala = await client.put(_url(narrative, "/moments/1"), json={"transicion": "Explosión"})
    assert mala.status_code == 422
    nadie = await client.put(_url(narrative, "/reader"), json={"lector": "Juana"})
    assert nadie.status_code == 422
    tipo = await client.put(_url(narrative, "/moments/1"), json={"tipo": "dibujo"})
    assert tipo.status_code == 422


async def test_descargar_el_txt_de_la_calabaza(client, monkeypatch):
    from src.application.services.video.config import video_config

    narrative = await _armado(client)
    await client.put(_url(narrative, "/presenter"), json={"intro": "Hola.", "outro": "Chau."})
    monkeypatch.setattr(video_config().presentador, "cierre_fijo", "Dejanos un like.")

    resp = await client.get(_url(narrative, "/calabaza.txt"))

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/plain; charset=utf-8"
    assert resp.headers["content-disposition"] == 'attachment; filename="calabaza-v1.txt"'
    assert resp.text == (
        "INTRO\nHola.\n\nOUTRO\nChau.\n\nCIERRE (igual en todos los episodios)\nDejanos un like.\n"
    )


# ── T4.2 / T4.3: los PDF ─────────────────────────────────────────────────────


def _pdf_text(data: bytes) -> tuple[int, str]:
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return len(reader.pages), "\n".join(p.extract_text() for p in reader.pages)


async def test_pdf_del_guion(client):
    narrative = await _armado(client)
    await client.put(_url(narrative, "/blocks/1"), json={"marcas": [[2, 3]]})
    await client.put(_url(narrative, "/reader"), json={"lector": "Yael"})
    await client.put(
        f"/api/v1/generated-narratives/{narrative.id}/acts/1",
        json={"text": "Párrafo 1 del acto 1, ¿qué? «Sí» — fin…\n\nPárrafo 2.\n\nPárrafo 3."},
    )

    resp = await client.get(_url(narrative, "/guion.pdf"))

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["content-disposition"] == 'attachment; filename="guion-v1.pdf"'
    pages, text = _pdf_text(resp.content)
    assert pages >= 6  # portada + un acto por hoja
    assert "LO LEE" in text and "Yael" in text
    assert "¿qué? «Sí» — fin…" in text  # tildes y signos, enteros
    assert "Hoja 1 de" in text
    assert "Cómo empieza" in text and "Cómo termina" in text


async def test_pdf_del_mapa(client):
    narrative = await _armado(client)

    resp = await client.get(_url(narrative, "/mapa.pdf"))

    assert resp.status_code == 200, resp.text
    pages, text = _pdf_text(resp.content)
    assert pages >= 2
    assert "MAPA DE PRODUCCIÓN" in text
    assert "ENTRA CUANDO DICE" in text
    assert "01-camino-1.png" in text
    assert "calabaza-v1-intro.mp3" in text
    assert "no people" in text  # el estilo va con el prompt


async def test_los_pdf_no_se_bajan_si_cambiaron_los_parrafos(client):
    narrative = await _armado(client)
    await client.put(f"/api/v1/generated-narratives/{narrative.id}/acts/2", json={"text": "Uno."})

    for nombre in ("guion.pdf", "mapa.pdf"):
        resp = await client.get(_url(narrative, f"/{nombre}"))
        assert resp.status_code == 409
        assert "acto 2" in resp.json()["detail"]


async def test_el_listado_dice_que_version_tiene_guion(client):
    narrative = await _armado(client)
    stories = (await client.get("/api/v1/stories")).json()
    mia = next(s for s in stories if s["id"] == str(narrative.story_template_id))
    assert mia["video_narrative_id"] == str(narrative.id)
