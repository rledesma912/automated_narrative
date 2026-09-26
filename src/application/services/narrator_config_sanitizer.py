"""Depuración del JSON `narrator_config` (Spec-190 §4.3, Slice 6).

El bloque `storyteller_config` del YAML trae datos que viven en tablas o columnas
propias (`scenarios`, `rules`, `entities`, `atmosphere`, `actos`) y, en los YAML
viejos, claves que ya no se usan (`voice_style`, `perception`, `knowledge`,
`language`, `bias`; Spec-530 §6). El JSON que se *persiste* como `narrator_config`
guarda solo quién narra y la voz gramatical.
"""

# Lo único que queda en el `narrator_config` persistido (Spec-530 §7).
_KEPT_KEYS = ("storyteller_id", "storyteller_name", "voice")
_VOICE_KEYS = ("person", "tense")


def sanitize_narrator_config(raw: dict | None) -> dict | None:
    """El config del narrador con solo `storyteller_id`, `storyteller_name` y `voice`."""
    if not raw:
        return raw
    kept = {k: raw[k] for k in _KEPT_KEYS if k in raw}
    if isinstance(kept.get("voice"), dict):
        kept["voice"] = {k: v for k, v in kept["voice"].items() if k in _VOICE_KEYS}
    return kept


def extract_atmosphere(raw: dict | None) -> tuple[str, str]:
    """Devuelve `(genero, subgenero)` desde `atmosphere` del config crudo (el `tone`
    de los YAML viejos se ignora: lo reemplaza el efecto buscado de la Dirección)."""
    atmosphere = (raw or {}).get("atmosphere") or {}
    return atmosphere.get("genre", "") or "", atmosphere.get("subgenre", "") or ""


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
