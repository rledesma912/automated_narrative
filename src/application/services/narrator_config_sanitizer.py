"""Depuración del JSON `narrator_config` (Spec-190 §4.3, Slice 6).

El bloque `storyteller_config` del YAML/wizard trae datos que ya viven en tablas
o columnas propias: `scenarios` y `rules` van a sus tablas, `atmosphere` pasa a
`genero`/`subgenero`/`tono`, y `actos` lo rutea el Slice 7. El JSON que se
*persiste* como `narrator_config` debe quedar sin esas cuatro claves.
"""

# Claves que no deben quedar dentro del `narrator_config` persistido.
_DROPPED_KEYS = ("scenarios", "rules", "actos", "atmosphere")


def sanitize_narrator_config(raw: dict | None) -> dict | None:
    """Devuelve el config del narrador sin `scenarios`/`rules`/`actos`/`atmosphere`.

    Conserva el resto tal cual: `storyteller_id`, `storyteller_name`,
    `voice_style`, `voice`, `perception`, `knowledge`, `language`, `bias`.
    """
    if not raw:
        return raw
    return {k: v for k, v in raw.items() if k not in _DROPPED_KEYS}
