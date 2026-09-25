"""Llamadas al LLM con salida JSON validada (Spec-530, decisión 8)."""

import json
import logging
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from src.config import settings
from src.domain.exceptions import LLMStructuredOutputError
from src.domain.interfaces import LLMProvider

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


async def generate_structured(
    llm: LLMProvider,
    *,
    role: str,
    prompt: str,
    system_prompt: str,
    output: type[T],
    retries: int = 1,
    min_predict: int | None = None,
) -> tuple[T, float]:
    """Pide al LLM un JSON que cumpla el esquema de `output` y lo valida.

    Reintenta `retries` veces ante un JSON inválido o que no valida; después lanza
    `LLMStructuredOutputError`. Nunca devuelve un resultado anterior en silencio.
    Devuelve el modelo validado y los segundos que tardó el LLM (sumando reintentos).
    """
    role_cfg = settings.role_config(role)
    schema = output.model_json_schema()
    elapsed = 0.0
    reason = ""
    for attempt in range(retries + 1):
        response = await llm.generate(
            prompt,
            system_prompt=system_prompt,
            role=role,
            model=role_cfg.get("model"),
            temperature=role_cfg.get("temperature"),
            num_ctx=role_cfg.get("num_ctx"),
            num_predict=max(role_cfg.get("num_predict") or 0, min_predict or 0) or None,
            response_schema=schema,
        )
        elapsed += response.elapsed_s or 0.0
        try:
            return output.model_validate(json.loads(_strip_fences(response.text))), elapsed
        except (json.JSONDecodeError, ValidationError) as e:
            reason = _short_reason(e)
            logger.warning(
                "[%s] JSON inválido (intento %d/%d): %s", role, attempt + 1, retries + 1, reason
            )
    raise LLMStructuredOutputError(role, reason)


def _strip_fences(text: str) -> str:
    """Algunos modelos envuelven el JSON en ```json … ``` aunque se pida el esquema."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        t = t.rsplit("```", 1)[0]
    return t.strip()


def _short_reason(error: Exception) -> str:
    if isinstance(error, ValidationError):
        first = error.errors()[0]
        return f"{'.'.join(str(p) for p in first['loc'])}: {first['msg']}"
    return str(error)[:200]
