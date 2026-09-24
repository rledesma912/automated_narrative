"""Spec-490 S0: formateo de un relato para el TTS."""

from datetime import UTC, datetime

import pytest

from src.application.services.narrative_script_formatter import (
    clean_prose,
    export_filename,
    split_acts,
    to_tts_markdown,
)
from src.utils import ARGENTINA_TZ

# --- T0.1: partir en actos -------------------------------------------------


def test_split_acts_formato_consolidado():
    content = "## Acto 1\n\nUno.\n\n## Acto 2\n\nDos.\n\nDos bis."
    assert split_acts(content) == [(1, "Uno."), (2, "Dos.\n\nDos bis.")]


def test_split_acts_acepta_legado_beat():
    assert split_acts("## Beat 3\n\nTres.") == [(3, "Tres.")]


def test_split_acts_sin_encabezados_es_preambulo():
    assert split_acts("Solo prosa.") == [(None, "Solo prosa.")]


def test_split_acts_preambulo_y_acto_vacio():
    content = "Antes.\n\n## Acto 1\n\n   \n\n## Acto 2\n\nDos."
    assert split_acts(content) == [(None, "Antes."), (2, "Dos.")]


def test_split_acts_vacio():
    assert split_acts("") == []
    assert split_acts(None) == []


def test_split_acts_crlf():
    assert split_acts("## Acto 1\r\n\r\nUno.") == [(1, "Uno.")]


# --- T0.2: limpiar la prosa ------------------------------------------------


def test_prosa_sin_marcas_no_cambia():
    prose = (
        "La casa estaba en silencio. Mi abuela, María, cerró la puerta —despacio— y apagó el farol."
    )
    assert clean_prose(prose) == [prose]


def test_un_parrafo_por_linea():
    assert clean_prose("Primera línea\nsigue acá.\n\nOtro párrafo.") == [
        "Primera línea sigue acá.",
        "Otro párrafo.",
    ]


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("- ¿Quién anda ahí? —pregunté.", "—¿Quién anda ahí? —pregunté."),
        ("-¿Quién?", "—¿Quién?"),
        ("– No mires.", "—No mires."),
        ("—Ya voy —dijo.", "—Ya voy —dijo."),
    ],
)
def test_guion_de_dialogo_pasa_a_raya(entrada, esperado):
    assert clean_prose(entrada) == [esperado]


def test_dialogos_seguidos_son_parrafos_distintos():
    assert clean_prose("- Hola.\n- Chau.") == ["—Hola.", "—Chau."]


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("*No mires atrás.* Eso decía.", "No mires atrás. Eso decía."),
        ("**Nunca** volví.", "Nunca volví."),
        ("Algo se movió, *despacio*, en el monte.", "Algo se movió, despacio, en el monte."),
        ("Lo llamaban _el Pombero_ en el pueblo.", "Lo llamaban el Pombero en el pueblo."),
        ("* Una viñeta suelta.", "Una viñeta suelta."),
    ],
)
def test_se_quita_el_enfasis(entrada, esperado):
    assert clean_prose(entrada) == [esperado]


def test_guion_bajo_interno_no_cambia():
    assert clean_prose("El archivo nota_final quedó ahí.") == ["El archivo nota_final quedó ahí."]


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("> Una cita.", "Una cita."),
        ("# Un título colado", "Un título colado"),
        ("### Otro", "Otro"),
        ("> - Diálogo citado.", "—Diálogo citado."),
    ],
)
def test_se_quitan_cita_y_encabezado(entrada, esperado):
    assert clean_prose(entrada) == [esperado]


@pytest.mark.parametrize("separador", ["---", "***", "* * *", "___", "- - -"])
def test_separadores_se_eliminan(separador):
    assert clean_prose(f"Antes.\n\n{separador}\n\nDespués.") == ["Antes.", "Después."]


def test_parrafo_entre_corchetes_pierde_los_corchetes():
    assert clean_prose("[Silencio en la casa.]") == ["Silencio en la casa."]


def test_corchetes_dentro_del_parrafo_no_cambian():
    assert clean_prose("Dijo [algo] y se fue.") == ["Dijo [algo] y se fue."]


# --- T0.3: el .md completo -------------------------------------------------


def test_to_tts_markdown_relato_de_tres_actos():
    content = (
        "## Acto 1\n\nLlegué al monte.\nEra de noche.\n\n- ¿Hay alguien?\n\n"
        "## Acto 2\n\n*Algo* respiraba.\n\n"
        "## Acto 3\n\nNunca volví."
    )
    assert to_tts_markdown("El monte prohibido", content) == (
        "# El monte prohibido\n\n"
        "## Acto 1\n\n"
        "Llegué al monte. Era de noche.\n\n"
        "—¿Hay alguien?\n\n"
        "[pause=1500]\n\n"
        "## Acto 2\n\n"
        "Algo respiraba.\n\n"
        "[pause=1500]\n\n"
        "## Acto 3\n\n"
        "Nunca volví.\n"
    )


def test_to_tts_markdown_sin_pausa_por_actos_omitidos():
    content = "## Acto 1\n\nUno.\n\n## Acto 2\n\n---\n\n## Acto 3\n\nTres."
    assert to_tts_markdown("T", content) == (
        "# T\n\n## Acto 1\n\nUno.\n\n[pause=1500]\n\n## Acto 3\n\nTres.\n"
    )


def test_to_tts_markdown_titulo_en_una_linea():
    assert to_tts_markdown("  La pena\ndel colectivo ", "## Acto 1\n\nUno.").startswith(
        "# La pena del colectivo\n\n"
    )


def test_to_tts_markdown_preambulo_antes_del_primer_acto():
    assert to_tts_markdown("T", "Intro.\n\n## Acto 1\n\nUno.") == (
        "# T\n\nIntro.\n\n## Acto 1\n\nUno.\n"
    )


# --- T0.4: nombre de archivo -----------------------------------------------

_AR_1530 = datetime(2026, 9, 24, 15, 30, tzinfo=ARGENTINA_TZ)


@pytest.mark.parametrize(
    ("titulo", "esperado"),
    [
        ("El monte prohibido", "el-monte-prohibido-2026-09-24-1530.md"),
        (
            "¿Quién llamó a la puerta? Año ñandú",
            "quien-llamo-a-la-puerta-ano-nandu-2026-09-24-1530.md",
        ),
        ("", "relato-2026-09-24-1530.md"),
        ("¿¡!?", "relato-2026-09-24-1530.md"),
    ],
)
def test_export_filename(titulo, esperado):
    assert export_filename(titulo, _AR_1530) == esperado


def test_export_filename_titulo_largo_recortado_sin_guion_final():
    name = export_filename("palabra " * 20, _AR_1530)
    slug = name.removesuffix("-2026-09-24-1530.md")
    assert len(slug) <= 60
    assert not slug.endswith("-")


def test_export_filename_convierte_utc_a_hora_argentina():
    utc = datetime(2026, 9, 24, 18, 30, tzinfo=UTC)
    assert export_filename("T", utc) == "t-2026-09-24-1530.md"


def test_export_filename_naive_se_toma_como_esta():
    assert export_filename("T", datetime(2026, 9, 24, 15, 30)) == "t-2026-09-24-1530.md"
