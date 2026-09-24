"""Spec-490 T0.5: contrato con el parser de `audiogen`.

Replica la regla con la que `audiogen/application/services/markdown_parser.py`
descarta líneas (vacías, las que empiezan con `#`, `-`, `*` o `>`, y los
comandos `^[...]$`) y verifica que ningún párrafo de prosa se pierda.
"""

import re

from src.application.services.narrative_script_formatter import to_tts_markdown

_COMMAND = re.compile(r"^\[.*\]$")

HOSTIL = """## Acto 1

- ¿Quién anda ahí? —pregunté.
- Nadie —respondió una voz.

*No mires atrás.* Eso me había dicho mi abuela.

> Una cita que la Voz dejó colada.

---

[Silencio en la casa.]

## Acto 2

# Un encabezado que no debía estar

**Nunca** volví al monte
aunque todavía lo sueño.

* * *

_El Pombero_ silbaba entre los árboles.

## Acto 3

– Ya es tarde —dijo mi madre.
"""

# Lo que la Voz escribió, sin las marcas que el export quita.
PARRAFOS_ESPERADOS = [
    "—¿Quién anda ahí? —pregunté.",
    "—Nadie —respondió una voz.",
    "No mires atrás. Eso me había dicho mi abuela.",
    "Una cita que la Voz dejó colada.",
    "Silencio en la casa.",
    "Un encabezado que no debía estar",
    "Nunca volví al monte aunque todavía lo sueño.",
    "El Pombero silbaba entre los árboles.",
    "—Ya es tarde —dijo mi madre.",
]


def _audiogen_segments(markdown: str) -> tuple[list[str], list[str], list[str]]:
    """(texto que se narra, líneas salteadas, comandos), como los ve `audiogen`."""
    narrated, skipped, commands = [], [], []
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("#", "-", "*", ">")):
            skipped.append(line)
        elif _COMMAND.match(line):
            commands.append(line)
        else:
            narrated.append(line)
    return narrated, skipped, commands


def test_toda_la_prosa_llega_al_tts():
    narrated, _, _ = _audiogen_segments(to_tts_markdown("El monte prohibido", HOSTIL))
    assert narrated == PARRAFOS_ESPERADOS


def test_solo_se_saltean_titulo_y_rotulos():
    _, skipped, commands = _audiogen_segments(to_tts_markdown("El monte prohibido", HOSTIL))
    assert skipped == ["# El monte prohibido", "## Acto 1", "## Acto 2", "## Acto 3"]
    assert commands == ["[pause=1500]", "[pause=1500]"]


def test_sin_marcas_hostiles_la_salida_no_tiene_nada_salteable():
    markdown = to_tts_markdown("T", "## Acto 1\n\nUno.\n\n—Dos —dijo.")
    narrated, skipped, commands = _audiogen_segments(markdown)
    assert narrated == ["Uno.", "—Dos —dijo."]
    assert skipped == ["# T", "## Acto 1"]
    assert commands == []
