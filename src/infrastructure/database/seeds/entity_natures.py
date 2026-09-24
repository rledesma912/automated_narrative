"""Catálogo de naturalezas de entidad y su mapeo por género (Spec-450 §1).

Seed de `init_db()`. A diferencia del catálogo de géneros, acá **el seed manda**:
las naturalezas se insertan con upsert, así que editar una etiqueta u orden en este
archivo llega a las bases existentes al reiniciar. El mapeo género → naturaleza
solo agrega pares (quitar uno del seed no lo borra de la DB).
"""

UNKNOWN_NATURE = "desconocida"

ENTITY_NATURES: list[tuple[str, str]] = [
    ("espiritu", "Espíritu / aparecido"),
    ("demonio", "Demonio"),
    ("criatura", "Criatura / monstruo"),
    ("humano", "Humano (asesino, acosador)"),
    ("culto", "Culto / colectivo"),
    ("contagio", "Contagio / organismo"),
    ("lugar", "Lugar vivo o maldito"),
    ("cosmica", "Entidad cósmica"),
    ("folklorica", "Ser del folklore"),
    (UNKNOWN_NATURE, "Desconocida / ambigua"),
]

# `desconocida` se suma a todos los géneros en `genre_nature_rows()`.
GENRE_ENTITY_NATURES: dict[str, list[str]] = {
    "terror_psicologico": ["humano", "espiritu", "lugar"],
    "horror_cosmico": ["cosmica", "culto", "criatura", "lugar"],
    "terror_gotico": ["espiritu", "demonio", "criatura", "lugar", "humano"],
    "body_horror": ["contagio", "criatura", "humano", "cosmica"],
    "paranormal": ["espiritu", "demonio", "lugar", "folklorica"],
    "folk_horror": ["folklorica", "espiritu", "culto", "lugar", "demonio"],
    "suspenso": ["humano", "culto"],
    "terror_supervivencia": ["criatura", "humano", "contagio", "culto"],
}


def nature_rows() -> list[tuple[str, str, int]]:
    """Filas `(id, label, order_index)` para `entity_nature`."""
    return [(nid, label, i) for i, (nid, label) in enumerate(ENTITY_NATURES, start=1)]


def genre_nature_rows() -> list[tuple[str, str]]:
    """Filas `(genre_id, nature_id)` para `genre_entity_nature`, con `desconocida` en todos."""
    return [
        (genre_id, nature_id)
        for genre_id, natures in GENRE_ENTITY_NATURES.items()
        for nature_id in [*natures, UNKNOWN_NATURE]
    ]
