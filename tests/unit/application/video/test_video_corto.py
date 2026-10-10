"""Spec-650 S4: el paquete para el video de un relato corto (3 actos, ~7 min)."""

import shutil
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.application.services import narrative_acts
from src.application.services.video import type_mix
from src.application.services.video.config import (
    estructura_del_relato,
    load_video_config,
    video_config,
)
from src.application.services.video.prompts import VideoScriptPrompts
from src.application.services.video.schema import BloqueIA, MomentoIA, PaqueteIA
from src.application.services.video.script_builder import VideoScriptBuilder
from src.application.services.video.service import VideoScriptService
from src.domain.models import GeneratedNarrative, Story
from src.infrastructure.adapters import MockLLMAdapter

CONFIG_DIR = Path(__file__).resolve().parents[4] / "config" / "video"


def _contenido(actos: int, parrafos: int) -> str:
    return "\n\n".join(
        f"## Acto {a}\n\n"
        + "\n\n".join(f"Párrafo {p} del acto {a}." for p in range(1, parrafos + 1))
        for a in range(1, actos + 1)
    )


CORTO = narrative_acts.split(_contenido(3, 4))  # 12 párrafos


def _momentos(n: int) -> list[MomentoIA]:
    """`n` momentos de un párrafo, repartidos en los 3 actos de 4 párrafos."""
    lugares = [(a, p) for a in range(1, 4) for p in range(1, 5)][:n]
    return [
        MomentoIA(
            acto=a,
            desde=p,
            hasta=p if i < n - 1 or n == 12 else 4,
            fuerte=i == 0,
            que_se_ve="La ruta",
            lugar="ruta",
            prompt_imagen="An empty road at night, 16:9",
            prompt_movimiento="Slow push-in.",
            transicion="Corte",
            sonido="Viento",
        )
        for i, (a, p) in enumerate(lugares)
    ]


def _paquete(n: int) -> PaqueteIA:
    bloques = [
        BloqueIA(acto=a, desde=1, hasta=4, indicacion="", enfasis=[], pausa="larga")
        for a in range(1, 4)
    ]
    return PaqueteIA(
        narra="hombre",
        bloques=bloques,
        momentos=_momentos(n),
        intro=" ".join(["Bienvenidos a mi cripta, pónganse cómodos."] * 10),
        outro=" ".join(["Conozco a algunos de ustedes, no me quedaría."] * 15) + " Buenas noches.",
    )


def _problemas_de_cantidad(n: int) -> list[str]:
    return [
        p
        for p in VideoScriptBuilder(video_config()).check(_paquete(n), CORTO)
        if p.startswith("Hay ")
    ]


def test_el_largo_del_relato_sale_de_cuantos_actos_tiene():
    assert estructura_del_relato(3) == "corto"
    assert estructura_del_relato(5) == "largo"
    assert estructura_del_relato(2) == "largo"  # cantidad rara: la de siempre


def test_el_corto_pide_entre_6_y_9_momentos():
    assert _problemas_de_cantidad(6) == []
    assert _problemas_de_cantidad(9) == []
    assert _problemas_de_cantidad(5) == ["Hay 5 momentos: tienen que ser entre 6 y 9."]
    assert _problemas_de_cantidad(10) == ["Hay 10 momentos: tienen que ser entre 6 y 9."]


def test_el_prompt_del_corto_pide_sus_momentos():
    story = Story(title="t", protagonista="Ana", relator="Primera persona", sinopsis="s")
    _, user = VideoScriptPrompts(video_config()).build(story, CORTO)
    assert "entre 6 y 9 momentos" in user
    _, largo = VideoScriptPrompts(video_config()).build(
        story, narrative_acts.split(_contenido(5, 3))
    )
    assert "entre 10 y 15 momentos" in largo


def test_los_videos_del_corto_entran():
    biblia = video_config().biblia.para("corto")
    tipos = type_mix.assign([False] * 7 + [True], biblia, seed=3)
    assert 1 <= tipos.count("video") <= 2


def test_el_episodio_del_corto():
    lectura = video_config().lectura
    assert lectura.episodio("corto").model_dump() == {"desde": 6, "hasta": 8}
    assert lectura.episodio("largo").model_dump() == {"desde": 12, "hasta": 17}


async def test_con_el_mock_sale_un_paquete_corto_valido():
    story = Story(title="t", protagonista="Ana", relator="Primera persona", sinopsis="s")
    narrative = GeneratedNarrative(story_template_id=story.id, title="v", content=_contenido(3, 4))
    script = await VideoScriptService(MockLLMAdapter()).generate(story, narrative)
    assert 6 <= len(script.momentos) <= 9
    assert set(script.parrafos_por_acto) == {1, 2, 3}


# ── La config tiene que traer los rangos de cada largo ────────────────────────


@pytest.fixture
def copia(tmp_path: Path) -> Path:
    destino = tmp_path / "video"
    shutil.copytree(CONFIG_DIR, destino)
    return destino


def _editar(directory: Path, archivo: str, fn) -> None:
    path = directory / archivo
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def test_sin_los_rangos_del_corto_no_carga(copia):
    _editar(copia, "biblia_visual.yaml", lambda d: d.pop("por_estructura"))
    with pytest.raises(ValidationError, match="corto"):
        load_video_config(copia)


def test_sin_el_episodio_del_corto_no_carga(copia):
    _editar(copia, "lectura.yaml", lambda d: d.pop("episodio_por_estructura"))
    with pytest.raises(ValidationError, match="corto"):
        load_video_config(copia)


def test_mas_videos_que_momentos_en_el_corto_no_carga(copia):
    _editar(
        copia,
        "biblia_visual.yaml",
        lambda d: d["por_estructura"]["corto"].update(videos={"desde": 1, "hasta": 7}),
    )
    with pytest.raises(ValidationError, match="videos"):
        load_video_config(copia)
