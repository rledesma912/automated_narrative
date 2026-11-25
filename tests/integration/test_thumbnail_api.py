"""Spec-790 §10.7: la miniatura por la API, con un ComfyUI de mentira (sin GPU)."""

import asyncio
import io
from collections.abc import AsyncIterator

import httpx
import pytest
from PIL import Image, ImageDraw

from src.config import settings
from src.infrastructure.database.connection import init_db
from src.main import app
from src.presentation import thumbnail_jobs
from tests.support.fake_comfy import FakeComfy

_PAYLOAD = {
    "title": "La torre",
    "protagonista": "Ernesto: guardabosques",
    "relator": "Primera persona en pasado. Narrador: Ernesto.",
    "escenarios": "La torre: una torre de vigilancia en el bosque",
    "sinopsis": "Un guardabosques ve algo entre los pinos.",
}


@pytest.fixture
async def client(monkeypatch, tmp_path) -> AsyncIterator[tuple[httpx.AsyncClient, FakeComfy]]:
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{tmp_path / 'th.db'}")
    monkeypatch.setattr(settings, "miniaturas_dir", str(tmp_path / "miniaturas"))
    fake = FakeComfy()
    monkeypatch.setattr(thumbnail_jobs, "comfy_client", lambda: fake)
    await init_db()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, fake


def _png(w=600, h=400, figura=True) -> bytes:
    im = Image.new("RGB", (w, h), (120, 120, 120))
    if figura:
        ImageDraw.Draw(im).rectangle((w * 0.4, h * 0.1, w * 0.6, h * 0.95), fill=(40, 40, 40))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


async def _story(c) -> str:
    resp = await c.post("/api/v1/stories?action=save", json=_PAYLOAD)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


async def _wait_job(c, job_id: str) -> dict:
    for _ in range(400):
        job = (await c.get(f"/api/v1/jobs/{job_id}")).json()
        if job["status"] in ("done", "failed"):
            return job
        await asyncio.sleep(0.05)
    raise AssertionError("el job no terminó")


async def test_sin_bocetos_no_arma(client):
    c, _ = client
    sid = await _story(c)
    vista = (await c.get(f"/api/v1/stories/{sid}/thumbnail")).json()
    assert vista["input"]["place_description"].startswith("La torre")  # el primer lugar (Spec-710)
    vista = (
        await c.put(
            f"/api/v1/stories/{sid}/thumbnail",
            json={"place_description": "Una torre en un bosque de pinos"},
        )
    ).json()
    assert vista["tono_propuesto"] == "verde"  # D25: «bosque»
    resp = await c.post(f"/api/v1/stories/{sid}/jobs", json={"kind": "thumbnail_build"})
    assert resp.status_code == 422


async def test_boceto_invalido(client):
    c, _ = client
    sid = await _story(c)
    resp = await c.post(
        f"/api/v1/stories/{sid}/thumbnail/sketches/personaje",
        files={"file": ("x.png", b"no es una imagen", "image/png")},
    )
    assert resp.status_code == 422


async def test_armar_las_4_y_recolorear(client):
    c, fake = client
    sid = await _story(c)
    for tipo in ("personaje", "escenario"):
        resp = await c.post(
            f"/api/v1/stories/{sid}/thumbnail/sketches/{tipo}",
            files={"file": (f"{tipo}.png", _png(figura=tipo == "personaje"), "image/png")},
        )
        assert resp.status_code == 200, resp.text
    resp = await c.put(
        f"/api/v1/stories/{sid}/thumbnail",
        json={
            "figure_description": "Una criatura altísima.",
            "place_description": "Una torre en un bosque",
        },
    )
    assert resp.status_code == 200

    resp = await c.post(f"/api/v1/stories/{sid}/jobs", json={"kind": "thumbnail_build"})
    assert resp.status_code == 202, resp.text
    job = await _wait_job(c, resp.json()["job_id"])
    assert job["status"] == "done", job

    vista = (await c.get(f"/api/v1/stories/{sid}/thumbnail")).json()
    tanda = vista["batches"][-1]
    assert [i["template"] for i in tanda["images"]] == [
        "A_der",
        "A_izq",
        "C_primer_plano",
        "B_lugar",
    ]
    assert tanda["tone"] == "verde"
    img = await c.get(f"/api/v1/stories/{sid}/thumbnail/images/1/A_der.jpg")
    assert img.status_code == 200
    assert Image.open(io.BytesIO(img.content)).size == (1280, 720)
    # una llamada por pieza y una por fundido (D15)
    assert fake.llamadas.count("boceto_a_imagen") == 2 + 4
    assert fake.llamadas.count("foto_img2img") == 2  # el escenario y el personaje (E11)

    # cambiar a blanco y negro recolorea sin GPU
    antes = len(fake.llamadas)
    vista = (await c.put(f"/api/v1/stories/{sid}/thumbnail", json={"color": "byn"})).json()
    assert len(fake.llamadas) == antes
    assert vista["batches"][-1]["color"] == "byn"
    im = Image.open(
        io.BytesIO((await c.get(f"/api/v1/stories/{sid}/thumbnail/images/1/B_lugar.jpg")).content)
    )
    r, g, b = im.convert("RGB").getpixel((640, 360))
    assert abs(r - g) <= 2 and abs(g - b) <= 2

    # otra tanda reusa el personaje y el escenario (no cambió nada)
    resp = await c.post(f"/api/v1/stories/{sid}/jobs", json={"kind": "thumbnail_build"})
    assert (await _wait_job(c, resp.json()["job_id"]))["status"] == "done"
    assert fake.llamadas.count("boceto_a_imagen") == 2 + 4 + 4
    assert fake.llamadas.count("foto_img2img") == 2  # reusa las dos piezas: ninguna foto nueva


async def test_avisa_si_la_compu_de_las_imagenes_esta_apagada(client):
    c, fake = client
    sid = await _story(c)
    assert (await c.get(f"/api/v1/stories/{sid}/thumbnail")).json()["comfy_disponible"] is True
    fake.vram = 0
    assert (await c.get(f"/api/v1/stories/{sid}/thumbnail")).json()["comfy_disponible"] is False
