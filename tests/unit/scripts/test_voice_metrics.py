"""Spec-470 T0.2: métricas de la prosa, con fragmentos reales de la S5 de Spec-450."""

from scripts.voice_metrics import (
    cliches,
    narrator_outside_dialogue,
    repeated_4grams,
    split_acts,
    valid_kinship,
    wrong_kinship,
)

CAST = [
    {"name": "Irene", "role": "Narradora y protagonista; nuera de María"},
    {"name": "Ricardo", "role": "Esposo de Irene; hijo de María"},
    {"name": "Mariano", "role": "Hijo pequeño de Irene y Ricardo"},
    {"name": "María", "role": "Suegra de Irene; madre de Ricardo; dueña de la casa"},
]


def test_cliches_sin_doble_conteo():
    text = (
        "Se me heló la sangre. Después, me heló la sangre otra vez y sentí un nudo en el estómago."
    )
    assert cliches(text) == {
        "se me heló la sangre": 1,
        "me heló la sangre": 1,
        "un nudo en el estómago": 1,
    }


def test_parentescos_validos_salen_de_los_roles():
    assert valid_kinship("Irene", CAST) == {"suegra", "esposo", "hijo"}


def test_mi_abuela_en_la_narracion_es_error():
    text = "¿Será que todo esto… que las leyendas de mi abuela… serán ciertas?"
    assert wrong_kinship(text, "Irene", CAST)["narracion"] == {"abuela": 1}


def test_mi_suegra_y_mi_esposo_son_correctos():
    text = "Mi suegra nos esperaba. Mi esposo tiró de las riendas; mi hijo lloraba."
    assert wrong_kinship(text, "Irene", CAST)["narracion"] == {}


def test_mi_madre_en_dialogo_va_aparte():
    text = "“Prometiste a mi madre…”, le dije.\n—Vamos a cenar, mamá."
    result = wrong_kinship(text, "Irene", CAST)
    assert result["narracion"] == {}
    assert result["dialogo"] == {"madre": 1}


def test_narradora_en_tercera_persona():
    text = (
        "Ricardo se sume en un silencio catatónico que Irene no se atreve a romper.\n"
        "—Irene, no seas supersticiosa.\n"
        "“Irene, por favor”, me interrumpió."
    )
    assert narrator_outside_dialogue(text, "Irene") == 1


def test_frases_repetidas_en_tres_actos():
    acts = [
        "el olor a tierra mojada me invadió",
        "de nuevo el olor a tierra mojada",
        "y otra vez el olor a tierra mojada",
    ]
    assert repeated_4grams(acts) == ["el olor a tierra", "olor a tierra mojada"]


def test_split_acts():
    assert split_acts("## Acto 1\n\nUno.\n\n## Acto 2\n\nDos.") == ["Uno.", "Dos."]
