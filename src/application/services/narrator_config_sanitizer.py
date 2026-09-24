"""Depuración del JSON `narrator_config` (Spec-190 §4.3, Slice 6).

El bloque `storyteller_config` del YAML/wizard trae datos que ya viven en tablas
o columnas propias: `scenarios`, `rules` y `entities` (Spec-450) van a sus tablas,
`atmosphere` pasa a `genero`/`subgenero`/`tono`, y `actos` lo rutea el Slice 7. El
JSON que se *persiste* como `narrator_config` debe quedar sin esas claves.
"""

# Claves que no deben quedar dentro del `narrator_config` persistido.
_DROPPED_KEYS = ("scenarios", "rules", "actos", "atmosphere", "entities")


def sanitize_narrator_config(raw: dict | None) -> dict | None:
    """Devuelve el config del narrador sin `scenarios`/`rules`/`actos`/`atmosphere`/`entities`.

    Conserva el resto tal cual: `storyteller_id`, `storyteller_name`,
    `voice_style`, `voice`, `perception`, `knowledge`, `language`, `bias`.
    """
    if not raw:
        return raw
    return {k: v for k, v in raw.items() if k not in _DROPPED_KEYS}


def extract_atmosphere(raw: dict | None) -> tuple[str, str, str]:
    """Devuelve `(genero, subgenero, tono)` desde `atmosphere` del config crudo."""
    atmosphere = (raw or {}).get("atmosphere") or {}
    return (
        atmosphere.get("genre", "") or "",
        atmosphere.get("subgenre", "") or "",
        atmosphere.get("tone", "") or "",
    )


def extract_actos(raw: dict | None) -> list[dict]:
    """Devuelve los 5 actos de `actos` del config crudo como `number`/`type`/`synopsis`.

    Un acto ausente se devuelve con valores vacíos.
    """
    actos = (raw or {}).get("actos") or {}
    result = []
    for i in range(1, 6):
        act_data = actos.get(f"act_{i}", {})
        result.append(
            {
                "number": i,
                "type": act_data.get("type", ""),
                "synopsis": act_data.get("text", ""),
            }
        )
    return result
