"""Spec-670: moldes de historia (base + forma + giro + largo).

Usa las mismas historias que los snapshots de siempre (`test_assistant_prompts_snapshot`,
`test_voice_prompts_snapshot`) con otra forma: así se ve qué cambia y, de paso, que las
respuestas de la forma de siempre (la transgresión de José) no se cuelan (D11).

Para regenerar los snapshots a propósito:
    SNAPSHOT_UPDATE=1 uv run pytest tests/unit/application/authoring/test_moldes.py
"""

import json
import os
from itertools import product
from pathlib import Path

import pytest

from src.application.services.authoring import catalog, context, molde, workshop_rules
from src.application.services.authoring.consultant import WorkshopConsultant
from src.application.services.authoring.outline_narrator import OutlineNarrator
from src.application.services.authoring.planner import OutlinePlanner
from src.application.services.authoring.verifier import OutlineVerifier
from src.application.services.beat_spec_repository import BeatSpecRepository
from src.domain.models import CriterionStatus, Story, WorkshopItem
from tests.unit.application.authoring import test_assistant_prompts_snapshot as asistente
from tests.unit.application.authoring import test_prompts_corto_snapshot as corto
from tests.unit.application.authoring import test_voice_prompts_snapshot as voz

SNAPSHOTS = Path(__file__).parents[3] / "fixtures" / "snapshots"
CAUSA = "Algo que cambió en la ruta lo empuja a subir al micro."


def _con_forma(story: Story, forma: str, giro: str = "", arco: str = "") -> Story:
    direction = story.direction.model_copy(
        update={"form": forma, "ingredient": giro, "form_other": arco}
    )
    workshop = [
        *story.workshop,
        WorkshopItem(criterion="asedio_causa", status=CriterionStatus.CUMPLE, answer=CAUSA),
    ]
    return story.model_copy(update={"direction": direction, "workshop": workshop})


# ── El catálogo ───────────────────────────────────────────────────────────────


def test_la_forma_de_siempre_es_la_de_antes():
    """D3: sin forma, los 9 criterios de antes en el mismo orden, sin intenciones ni
    reglas propias (los snapshots de siempre lo confirman byte a byte)."""
    m = molde.default()
    assert m.forma.id == "regla"
    assert m.ids == (
        "meta",
        "inquietud",
        "en_juego",
        "vulnerabilidad",
        "transgresion",
        "historia_secreta",
        "descubrimiento",
        "reaccion",
        "final",
    )
    assert m.reglas == () and m.intencion(2, "la de la estructura") == "la de la estructura"


def test_cada_forma_esta_completa_en_los_dos_largos():
    estructuras = BeatSpecRepository()
    for f in molde.catalogo().formas[1:]:
        for sid in estructuras.structure_ids:
            numeros = estructuras.estructura(sid).numeros
            assert sorted(f.actos[sid]) == numeros, (f.id, sid)
            assert all(f.actos[sid].values()), (f.id, sid)


@pytest.mark.parametrize("sid", ["largo", "corto"])
def test_tope_de_preguntas(sid):
    """D10: ninguna combinación del catálogo pasa de 9 preguntas sin giro ni de 10 con
    giro (hoy son 9 fijas): ampliar el catálogo no vuelve al formulario gigante."""
    cat = molde.catalogo()
    for forma, giro in product(cat.formas, (None, *cat.giros)):
        n = len(molde.Molde(forma, giro, sid).criterios)
        assert n <= (10 if giro else 9), (forma.id, giro and giro.id, n)


def test_los_criterios_del_molde_estan_en_el_banco_y_no_se_repiten():
    banco = [c.id for c in catalog.criteria_bank()]
    assert len(banco) == len(set(banco))
    cat = molde.catalogo()
    for forma, giro in product(cat.formas, (None, *cat.giros)):
        ids = molde.Molde(forma, giro, "largo").ids
        assert len(ids) == len(set(ids))


def test_forma_o_giro_que_ya_no_existe_cae_a_la_de_siempre():
    """D16."""
    story = _con_forma(asistente._story(), "una-que-se-borro", giro="otro-que-no-esta")
    m = molde.for_story(story)
    assert (m.forma.id, m.giro) == ("regla", None)


# ── D11: solo los criterios del molde llegan a la IA ──────────────────────────


def test_las_respuestas_de_otra_forma_no_se_cuelan():
    story = _con_forma(asistente._story(), "asedio")
    assert "transgresion" not in {cid for cid, _, _ in context.decisions(story)}
    assert "asedio_causa" in {cid for cid, _, _ in context.decisions(story)}
    texto = "\n".join(_asistente(story).values())
    assert "Mira el espejo aunque sabe que no tiene que hacerlo" not in texto
    assert CAUSA in texto


# ── Snapshots de «Algo viene por nosotros» (largo y corto) ────────────────────


def _asistente(story: Story) -> dict[str, str]:
    # Lo pendiente como lo arma el Consultor de verdad: los criterios del molde.
    items = workshop_rules.initial_items(
        story.direction, story.workshop, molde.for_story(story).criterios
    )
    pending = workshop_rules.to_evaluate(items)
    planner = OutlinePlanner(llm=None)
    return {
        "consultor": WorkshopConsultant(llm=None)._prompt(story, pending),
        "planificador_system": planner.system_prompt(story),
        "planificador": planner._prompt(story),
        "verificador": OutlineVerifier(llm=None)._prompt(story, story.outline),
    }


def _voz(story: Story) -> list[dict[str, str]]:
    narrator = OutlineNarrator(llm=None)
    out = []
    for act in story.outline:
        previous = "Primer párrafo.\n\nEl micro siguió por la ruta." if act.number > 1 else ""
        system, user = narrator.voice_prompts(story, act, voz._memory(act.number), previous)
        out.append({"acto": act.number, "system": system, "user": user})
    return out


def _asedio() -> dict:
    largo_a = _con_forma(asistente._story(), "asedio", giro="regla_rara")
    largo_v = _con_forma(voz._story(), "asedio")
    return {
        "largo": {"asistente": _asistente(largo_a), "voz": _voz(largo_v)},
        "corto": {
            "asistente": _asistente(corto._corto(largo_a)),
            "voz": _voz(corto._corto(largo_v)),
        },
    }


def test_prompts_de_asedio_no_cambian():
    prompts = _asedio()
    file = SNAPSHOTS / "moldes_asedio_prompts.json"
    if os.environ.get("SNAPSHOT_UPDATE"):
        file.write_text(json.dumps(prompts, ensure_ascii=False, indent=2) + "\n", "utf-8")
    assert prompts == json.loads(file.read_text("utf-8"))


@pytest.mark.parametrize("sid", ["largo", "corto"])
def test_asedio_no_pide_romper_una_regla_ni_una_culpa(sid):
    p = _asedio()[sid]
    planificador = p["asistente"]["planificador"]
    voz_texto = "\n".join(x["user"] for x in p["voz"])
    for texto in (planificador, voz_texto):
        assert "romper la regla" not in texto
        assert "transgresion" not in texto and "transgresión" not in texto
    assert "la amenaza se acerca paso a paso" in planificador
    assert "la amenaza se acerca paso a paso" in voz_texto  # la Voz recibe lo del acto
    # D15: lo que se revela es la causa, en el acto `revela_secreto` de la estructura.
    assert "acá se entiende qué empuja a la amenaza a venir" in planificador
    assert "historia secreta" not in planificador
    # Las reglas de la forma y del giro, al final de las de siempre.
    system = p["asistente"]["planificador_system"]
    assert system.endswith(
        "- La regla rara de la amenaza aparece en un hecho antes del último acto y decide cómo termina."
    )
    assert "- Nadie provoca a la amenaza: viene por una causa de afuera." in system
    # Las preguntas: las de la forma y la del giro, no las de la forma de siempre.
    consultor = p["asistente"]["consultor"]
    assert "- asedio_acercamiento:" in consultor and "- regla_de_la_amenaza:" in consultor
    assert "- vulnerabilidad:" not in consultor


def test_otra_lleva_el_arco_del_autor_y_ninguna_pregunta_de_forma():
    """D14: «Otra»: solo la base, intenciones neutras y cómo contó el autor su historia."""
    story = _con_forma(
        asistente._story(), "otra", arco="Un micro que cada noche tiene un pasajero menos."
    )
    m = molde.for_story(story)
    assert m.ids == ("meta", "inquietud", "en_juego", "reaccion", "final")
    planificador = OutlinePlanner(llm=None)._prompt(story)
    assert "CÓMO ES ESTA HISTORIA (la contó el autor" in planificador
    assert "Un micro que cada noche tiene un pasajero menos." in planificador
    assert "romper la regla" not in planificador and "transgresi" not in planificador


# ── S2: las formas y los giros nuevos ─────────────────────────────────────────

NUEVAS = ["lugar", "casa", "senuelo", "otra"]


def _formas() -> dict:
    out = {}
    for forma in NUEVAS:
        story = _con_forma(
            asistente._story(), forma, arco="Un micro que cada noche lleva un pasajero menos."
        )
        for sid, s in (("largo", story), ("corto", corto._corto(story))):
            p = _asistente(s)
            out[f"{forma}/{sid}"] = {
                k: p[k] for k in ("consultor", "planificador_system", "planificador")
            }
    return out


def test_prompts_de_las_formas_nuevas_no_cambian():
    prompts = _formas()
    file = SNAPSHOTS / "moldes_formas_prompts.json"
    if os.environ.get("SNAPSHOT_UPDATE"):
        file.write_text(json.dumps(prompts, ensure_ascii=False, indent=2) + "\n", "utf-8")
    assert prompts == json.loads(file.read_text("utf-8"))


@pytest.mark.parametrize("clave", [f"{f}/{s}" for f in NUEVAS for s in ("largo", "corto")])
def test_ninguna_forma_nueva_pide_romper_una_regla(clave):
    p = _formas()[clave]
    assert "romper la regla" not in p["planificador"]
    assert "transgresi" not in p["planificador"] and "- transgresion:" not in p["consultor"]
    assert "historia secreta" not in p["planificador"]


def _linea_del_acto(planificador: str, n: int) -> str:
    return next(line for line in planificador.splitlines() if line.startswith(f"{n}. "))


def test_cada_forma_revela_en_su_acto():
    """Ajuste de la S2: «Alguien que llega a casa» revela en el peor momento (acto 3 del
    largo), no en el acto del secreto de siempre (4); «Un lugar…» usa el de siempre."""
    casa = _con_forma(asistente._story(), "casa")
    casa = casa.model_copy(
        update={
            "workshop": [
                *casa.workshop,
                WorkshopItem(
                    criterion="casa_verdad",
                    status=CriterionStatus.CUMPLE,
                    answer="Tiene patas de cabra.",
                ),
            ]
        }
    )
    plan = OutlinePlanner(llm=None)._prompt(casa)
    assert "acá se ve lo que es en realidad el que llegó" in _linea_del_acto(plan, 3)
    assert "acá se ve lo que es" not in _linea_del_acto(plan, 4)

    lugar = _con_forma(asistente._story(), "lugar")
    lugar = lugar.model_copy(
        update={
            "workshop": [
                *lugar.workshop,
                WorkshopItem(
                    criterion="lugar_pasado",
                    status=CriterionStatus.CUMPLE,
                    answer="Ahí hubo un accidente.",
                ),
            ]
        }
    )
    plan = OutlinePlanner(llm=None)._prompt(lugar)
    assert "acá se entiende qué pasó en ese lugar antes" in _linea_del_acto(plan, 4)


def test_un_giro_no_va_con_la_forma_que_ya_pregunta_lo_mismo():
    """Ajuste de la S2: «El lugar tiene su propia historia» no se ofrece con «Un lugar que no
    hay que pisar» (repetiría «Qué pasó ahí antes»); si llega igual, se ignora."""
    cat = molde.catalogo()
    assert "lugar_historia" not in {g.id for g in cat.giros_para("lugar")}
    assert "lugar_historia" in {g.id for g in cat.giros_para("casa")}
    story = _con_forma(asistente._story(), "lugar", giro="lugar_historia")
    assert molde.for_story(story).giro is None
