from src.application.services.authoring.outline_narrator import (
    OutlineNarrator,
    merge_motifs,
    word_range,
)
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
    assert "Acto 1: José termina el turno.\nEstado: Cansado" in user
    assert "- olor a flores\n- «¿Todo bien, José?»" in user
    assert "EXTENSIÓN: entre 200 y 280 palabras." in user
    assert "RESONANCIA" not in user and "FIDELIDAD" not in user


def test_el_acto_5_cierra_con_el_final_del_autor(story):
    story = _story(story)
    _, user = OutlineNarrator(ScriptedLLM()).voice_prompts(story, story.outline[4], None)
    assert (
        "QUÉ TIENE QUE LOGRAR ESTE ACTO: cerrar la historia con el final que decidió el autor: Descansa en paz."
        in user
    )
    assert "escape incompleto" not in user
    assert "(es el comienzo del relato)" in user and "(nada todavía)" in user


def test_extension_proporcional():
    assert word_range(ActOutline(number=1, events=["a"])) == (200, 250)
    assert word_range(ActOutline(number=3, events=["a"] * 4)) == (410, 500)
    assert word_range(ActOutline(number=2, events=["a"] * 9)) == (460, 550)
    assert word_range(ActOutline(number=5, events=["a"] * 6)) == (150, 280)


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
            "motivos_usados": ["la radio que se corta", "olor a flores"],
        }
    )
    previous = NarrativeJournal(
        last_events="Acto 1: termina el turno.", used_motifs=["olor a flores"]
    )

    memory = await OutlineNarrator(llm).remember(
        story, story.outline[1], "Texto del acto 2", previous
    )

    assert memory.last_events == "Acto 1: termina el turno.\nActo 2: Frena y baja."
    assert memory.physical_emotional_state == "Asustado en la banquina."
    assert memory.used_motifs == ["olor a flores", "la radio que se corta"]
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
