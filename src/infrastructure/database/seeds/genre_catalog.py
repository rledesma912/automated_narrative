"""Catálogo de géneros y subgéneros v2 (Spec-440 §2).

Seed de `init_db()`: se inserta con `INSERT OR IGNORE`, así que solo puebla una
DB nueva. Una vez creada, la DB manda. Cada género suma el subgénero `otro`.
"""

OTHER_SUBGENRE = ("otro", "Otro estilo")

GENRE_CATALOG: list[tuple[str, str, list[tuple[str, str]]]] = [
    (
        "terror_psicologico",
        "Terror Psicológico",
        [
            ("paranoia", "Paranoia y persecución"),
            ("culpa_trauma", "Culpa y trauma"),
            ("locura", "Descenso a la locura"),
            ("doble", "El doble / identidad fracturada"),
            ("domestico", "Terror doméstico (familia, hogar)"),
            ("aislamiento", "Aislamiento y soledad"),
        ],
    ),
    (
        "horror_cosmico",
        "Horror Cósmico",
        [
            ("lovecraftiano", "Lovecraftiano clásico"),
            ("culto_prohibido", "Cultos y saberes prohibidos"),
            ("dimensional", "Otras dimensiones"),
            ("abismal", "Horror oceánico / abismal"),
            ("ciencia_prohibida", "Ciencia prohibida / experimento"),
        ],
    ),
    (
        "terror_gotico",
        "Terror Gótico",
        [
            ("gotico_clasico", "Gótico clásico (casonas, castillos)"),
            ("maldicion_familiar", "Maldición familiar / linaje"),
            ("vampirico", "Vampírico"),
            ("gotico_criollo", "Gótico criollo / sureño (decadencia rural)"),
            ("amor_maldito", "Romance oscuro / amor maldito"),
        ],
    ),
    (
        "body_horror",
        "Horror Corporal",
        [
            ("mutacion", "Mutación y transformación"),
            ("contagio", "Infección y contagio"),
            ("quirurgico", "Médico / quirúrgico"),
            ("parasitario", "Parásitos y simbiosis"),
            ("decadencia", "Enfermedad y decadencia del cuerpo"),
        ],
    ),
    (
        "paranormal",
        "Fenómenos Paranormales",
        [
            ("casa_embrujada", "Casa embrujada"),
            ("posesion", "Posesión"),
            ("fantasmas", "Fantasmas y aparecidos"),
            ("poltergeist", "Poltergeist"),
            ("leyenda_urbana", "Leyenda urbana"),
            ("objeto_maldito", "Objetos y lugares malditos"),
        ],
    ),
    (
        "folk_horror",
        "Terror Rural",
        [
            ("rural", "Leyendas del campo"),
            ("mitologia_regional", "Mitología regional (Luz Mala, Pombero…)"),
            ("culto_pagano", "Cultos paganos y rituales"),
            ("pueblo_aislado", "Pueblo aislado / comunidad cerrada"),
            ("brujeria", "Brujería y curanderismo"),
        ],
    ),
    (
        "suspenso",
        "Suspenso / Thriller",
        [
            ("misterio", "Misterio / enigma"),
            ("policial_noir", "Policial / noir"),
            ("acecho", "Acecho"),
            ("invasion_hogar", "Invasión del hogar"),
            ("conspiracion", "Conspiración"),
        ],
    ),
    (
        "terror_supervivencia",
        "Terror de Supervivencia",
        [
            ("slasher", "Slasher"),
            ("criaturas", "Criaturas y monstruos"),
            ("apocalipsis", "Apocalipsis / infectados"),
            ("naturaleza_hostil", "Naturaleza hostil"),
            ("encierro", "Encierro / trampa"),
        ],
    ),
]


def genre_rows() -> list[tuple[str, str, int]]:
    """Filas `(id, label, order_index)` para la tabla `genre`."""
    return [(gid, label, i) for i, (gid, label, _) in enumerate(GENRE_CATALOG, start=1)]


def subgenre_rows() -> list[tuple[str, str, str, int]]:
    """Filas `(genre_id, id, label, order_index)` para `subgenre`, con `otro` al final."""
    rows = []
    for gid, _, subs in GENRE_CATALOG:
        for i, (sid, label) in enumerate([*subs, OTHER_SUBGENRE], start=1):
            rows.append((gid, sid, label, i))
    return rows
