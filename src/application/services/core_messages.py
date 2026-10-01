"""Mensajes del Core que llegan a la pantalla, desde `config/core_messages.yaml` (Spec-620)."""

from functools import lru_cache
from pathlib import Path

import yaml

_DEFAULT_PATH = Path(__file__).resolve().parents[3] / "config" / "core_messages.yaml"


class MessageCatalog:
    """Mensajes por clave con puntos (`workshop.listo`), formateados con `str.format`.

    Una clave o un dato que falta es un error: un mensaje nunca sale vacío ni con un
    `{placeholder}` sin llenar.
    """

    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._messages = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def get(self, key: str, **data: object) -> str:
        node: object = self._messages
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                raise KeyError(f"Mensaje inexistente: {key}")
            node = node[part]
        if not isinstance(node, str):
            raise KeyError(f"La clave {key} no es un mensaje")
        return node.format(**data)


@lru_cache
def _catalog() -> MessageCatalog:
    return MessageCatalog()


def message(key: str, **data: object) -> str:
    """El mensaje de `key` del catálogo de `config/core_messages.yaml`."""
    return _catalog().get(key, **data)
