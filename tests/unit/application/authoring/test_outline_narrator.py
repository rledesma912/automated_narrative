from src.application.services.authoring.outline_narrator import (
    OutlineNarrator,
    merge_motifs,
    word_range,
)
from src.application.services.repetition_check import ActRepetition
from src.domain.models import ActOutline, NarrativeJournal, TypedRule
from tests.unit.application.authoring.conftest import ScriptedLLM


def _story(story):
    return story.model_copy(
        update={
            "personajes_full": [
                {"name": "José", "role": "Chofer"},
                {
                    "name": "El sereno",
                    "role": "",
                    "kind": "sin_nombre",
                    "relation": "Lo conozco de vista",
                },
                {
                    "name": "Su hija",
                    "role": "",
                    "kind": "sin_nombre",
                    "relation": "Mi hija, internada",
                },
            ],
            "typed_rules": [
                TypedRule(
                    id="r1",
                    story_id=story.id,
                    content="Solo aparece si está solo",
                    applies_to_beat=2,
                ),
            ],
            "outline": [ActOutline(number=n, events=[f"Hecho {n}"]) for n in range(1, 6)],
        }
    )


def test_prompt_de_la_voz_con_escaleta(story):
    story = _story(story)
    act = ActOutline(
        number=2,
        goal="Seguir manejando",
        events=["Ve a la mujer en el espejo", "Frena de golpe"],
        change_to="Duda de lo que ve",
        scenario="La ruta de noche",
        on_stage=["El sereno"],
        held_back="Quién es ella",
    )
    memory = NarrativeJournal(
        last_events="Acto 1: José termina el turno.",
        physical_emotional_state="Cansado",
        used_motifs=["olor a flores", "«¿Todo bien, José?»"],
        body_state="Un corte en la mano izquierda.",
        narrator_traits=["toma mate amargo", "odia llegar tarde"],
    )

    system, user = OutlineNarrator(ScriptedLLM()).voice_prompts(story, act, memory)

    assert system.startswith("Sos José y contás en primera persona")
    assert "Contalo como un caso que le contás a unos amigos" in system
    assert "Perfil del Narrador" not in system and "Percepción" not in system
    assert "El sereno" in system  # parentescos: solo quienes están en escena
    assert "Su hija" not in system and "Su hija" not in user
    assert "EVENTOS DE ESTE ACTO" in user and "- Frena de golpe" in user
    assert "No inventes nombres propios" in system
    assert "EN ESCENA: José, El sereno" in user
    assert "REGLAS DE ESTE ACTO:\n- Solo aparece si está solo" in user
    assert "NO REVELES TODAVÍA: Quién es ella" in user
    # Spec-590 E: lo que ya pasó sale de la escaleta; el cuerpo y el estado, de la memoria.
    assert "LO QUE YA PASÓ (no lo vuelvas a contar):\nActo 1: Hecho 1\n" in user
    assert "José termina el turno" not in user
    assert (
        "CÓMO ESTÁ JOSÉ AHORA (no lo contradigas): Cansado Un corte en la mano izquierda." in user
    )
    assert "Estado:" not in user
    # Spec-590 C: los rasgos que inventó la Voz vuelven para sostenerlos.
    assert "ASÍ ES JOSÉ (mantenelo; podés sumar):\n- toma mate amargo\n- odia llegar tarde" in user
    # Spec-590: la premisa, sin adelantar lo que no está en los eventos.
    assert (
        "LA HISTORIA, PARA QUE CONOZCAS A JOSÉ Y SU MUNDO (no cuentes nada de acá que no esté "
        "en los EVENTOS de este acto): José ve por el espejo a una mujer que murió en su micro."
    ) in user
    assert "- olor a flores\n- «¿Todo bien, José?»" in user
    assert "contá cada evento en un párrafo" in user
    assert "en total, entre 200 y 260 palabras." in user
    # Spec-590 B y C: sin diálogo directo; rasgos y gestos chicos inventados por la Voz.
    assert "Nunca escribas diálogo: ni rayas ni comillas" in system
    assert "Si hay diálogo" not in system
    assert "tus gustos, tus manías y alguna inseguridad tuya" in system
    assert "RESONANCIA" not in user and "FIDELIDAD" not in user


def test_el_acto_5_cierra_con_el_final_del_autor(story):
    story = _story(story)
    _, user = OutlineNarrator(ScriptedLLM()).voice_prompts(story, story.outline[4], None)
    assert (
        "QUÉ TIENE QUE LOGRAR ESTE ACTO: cerrar la historia con el final que decidió el autor: Descansa en paz."
        in user
    )
    assert "escape incompleto" not in user
    assert "Acto 1: Hecho 1\nActo 2: Hecho 2\nActo 3: Hecho 3\nActo 4: Hecho 4" in user
    assert "(nada todavía)" in user and "CÓMO ESTÁ" not in user and "ASÍ ES" not in user


def test_extension_proporcional():
    # Spec-610 D11: 100 palabras por evento, entre 250 y 500; el desenlace, 180–300.
    assert word_range(ActOutline(number=1, events=["a"])) == (200, 250)
    assert word_range(ActOutline(number=3, events=["a"] * 4)) == (360, 460)
    assert word_range(ActOutline(number=2, events=["a"] * 9)) == (400, 500)
    assert word_range(ActOutline(number=5, events=["a"] * 6)) == (180, 300)


def test_motivos_sin_repetir():
    assert merge_motifs(["Olor a flores"], ["olor a flores", "la radio que se corta", " "]) == [
        "Olor a flores",
        "la radio que se corta",
    ]


async def test_la_memoria_acumula_hechos_y_motivos(story):
    story = _story(story)
    llm = ScriptedLLM(
        {
            "hechos": "Frena y baja.",
            "estado": "Asustado en la banquina.",
            "cuerpo": "Un corte en la mano izquierda y la camisa rota.",
            "asi_es": ["odia llegar tarde", "Toma mate amargo"],
            "motivos_usados": ["la radio que se corta", "olor a flores"],
        }
    )
    previous = NarrativeJournal(
        last_events="Acto 1: termina el turno.",
        used_motifs=["olor a flores"],
        body_state="Un corte en la mano izquierda.",
        narrator_traits=["toma mate amargo"],
    )

    memory = await OutlineNarrator(llm).remember(
        story, story.outline[1], "Texto del acto 2", previous
    )

    assert memory.last_events == "Acto 1: termina el turno.\nActo 2: Frena y baja."
    assert memory.physical_emotional_state == "Asustado en la banquina."
    assert memory.used_motifs == ["olor a flores", "la radio que se corta"]
    # Spec-590: el cuerpo y los rasgos; la memoria anterior llega al prompt para conservarlos.
    assert memory.body_state == "Un corte en la mano izquierda y la camisa rota."
    assert memory.narrator_traits == ["toma mate amargo", "odia llegar tarde"]
    assert (
        "CÓMO ESTABA EL CUERPO DE QUIEN NARRA: Un corte en la mano izquierda."
        in (llm.calls[0]["prompt"])
    )
    assert "ASÍ ES QUIEN NARRA (ya anotado):\n- toma mate amargo" in llm.calls[0]["prompt"]
    assert llm.calls[0]["role"] == "journal"
    assert llm.calls[0]["num_predict"] >= 700  # el JSON con motivos no entra en 256
    assert "Texto del acto 2" in llm.calls[0]["prompt"]


def test_la_escena_incluye_a_quien_nombran_los_eventos(story):
    story = story.model_copy(
        update={
            "personajes_full": [
                {"name": "José", "role": "Chofer"},
                {"name": "María", "role": "Suegra de José"},
                {"name": "Ricardo", "role": "Hermano de José"},
            ]
        }
    )
    act = ActOutline(
        number=4,
        events=["José piensa en lo que le dijo María."],
        on_stage=["Ricardo (de espaldas)"],
    )
    system, user = OutlineNarrator(ScriptedLLM()).voice_prompts(story, act, None)
    assert "EN ESCENA: José, María, Ricardo" in user
    assert "María" in system and "Suegra" in system


# ── Spec-560 A1: la Voz abre el acto con el puente y sigue desde el anterior ──


def test_la_voz_recibe_el_puente_y_el_final_del_acto_anterior(story):
    act = ActOutline(number=2, events=["Algo pasa"], bridge="Esa misma noche vuelve a la terminal.")
    previo = "Primer párrafo, que no va.\n\nSegunda oración. Tercera, larga. Cuarta y última."
    _, user = OutlineNarrator(ScriptedLLM()).voice_prompts(story, act, None, previo)
    assert "CÓMO SE LLEGA A ESTE ACTO" in user and "Esa misma noche vuelve a la terminal." in user
    assert "ASÍ TERMINÓ EL ACTO ANTERIOR" in user
    # Spec-590: el último párrafo entero (antes, 3 oraciones sueltas).
    assert "«Segunda oración. Tercera, larga. Cuarta y última.»" in user
    assert "Primer párrafo" not in user


def test_el_ultimo_parrafo_largo_se_corta_en_120_palabras(story):
    act = ActOutline(number=2, events=["Algo pasa"])
    largo = " ".join(f"Oración número {i} con varias palabras de relleno." for i in range(40))
    _, user = OutlineNarrator(ScriptedLLM()).voice_prompts(story, act, None, largo)
    final = user.split("ASÍ TERMINÓ EL ACTO ANTERIOR (seguí desde acá; no lo repitas):\n«")[1]
    final = final.split("»")[0]
    assert final.endswith("Oración número 39 con varias palabras de relleno.")
    assert 100 < len(final.split()) <= 120


def test_ya_usado_no_prohibe_lo_que_el_acto_tiene_que_mostrar(story):
    """Spec-590: «ojos brillantes» y «susurros» son lo que piden los eventos."""
    act = ActOutline(
        number=3,
        events=["Ve siluetas con ojos muy brillantes entre los árboles y oye susurros."],
    )
    memory = NarrativeJournal(used_motifs=["ojos brillantes", "susurros", "el olor a gasoil"])
    _, user = OutlineNarrator(ScriptedLLM()).voice_prompts(story, act, memory)
    ya_usado = user.split("YA USADO EN ACTOS ANTERIORES")[1].split("EXTENSIÓN")[0]
    assert "- el olor a gasoil" in ya_usado
    assert "ojos brillantes" not in ya_usado and "susurros" not in ya_usado


def test_el_acto_1_no_tiene_puente_ni_final_anterior(story):
    act = ActOutline(number=1, events=["Algo pasa"], bridge="no se usa en el acto 1")
    _, user = OutlineNarrator(ScriptedLLM()).voice_prompts(story, act, None, "")
    assert "CÓMO SE LLEGA" not in user and "ASÍ TERMINÓ" not in user


# ── Spec-590 T1.4: al regenerar, la Voz sabe si el acto estaba cortado o con diálogo ──


def test_avoid_avisa_oraciones_cortadas_y_dialogo():
    rep = ActRepetition(
        number=2, cut_sentences=["Un sonido.", "Más cerca."], cut_count=12, cut_pct=40, dialogue=2
    )
    text = OutlineNarrator(llm=None)._avoid(rep)
    assert "EN LA VERSIÓN ANTERIOR DE ESTE ACTO" in text
    assert "Tenía 12 oraciones cortadas (por ejemplo: «Un sonido.», «Más cerca.»)" in text
    assert "Tenía diálogo: contá lo que dicen, sin rayas ni comillas" in text


def test_avoid_no_avisa_un_fragmento_suelto():
    rep = ActRepetition(number=2, cut_sentences=["Solo."], cut_count=1, cut_pct=5)
    assert OutlineNarrator(llm=None)._avoid(rep) == ""


def test_avoid_arma_las_frases_repetidas_desde_los_datos():
    """Spec-620: `repeated` son datos (frase, acto); el texto sale del fragmento."""
    rep = ActRepetition(number=3, repeated=[("el olor dulce", 1)], cliches=["me heló la sangre"])
    assert OutlineNarrator(llm=None)._avoid(rep) == (
        "EN LA VERSIÓN ANTERIOR DE ESTE ACTO PASÓ ESTO — NO LO VUELVAS A HACER:\n"
        "- Repetiste «el olor dulce» (del acto 1)\n"
        "- Cliché: «me heló la sangre»\n\n"
    )


def test_la_premisa_llega_solo_con_su_primera_oracion(story):
    """Spec-590 (S3): el resto de la premisa adelantaba hechos (las astas en el acto 1)."""
    story = _story(story)
    story.direction.premise = (
        "Un camionero se queda varado en el bosque. Ve siluetas con astas. ¿Quiénes son?"
    )
    _, user = OutlineNarrator(ScriptedLLM()).voice_prompts(story, story.outline[0], None)

    assert (
        "MUNDO (no cuentes nada de acá que no esté en los EVENTOS de este acto): "
        "Un camionero se queda varado en el bosque.\n" in user
    )
    assert "astas" not in user
