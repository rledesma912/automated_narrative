"""Adapter de la API de OpenAI (Spec-740 Parte F).

Hecho a semejanza de `AnthropicAdapter`, no del de FreeLLMAPI (D9): es pago, responde el
modelo que se pidió y, si no atiende, el job falla enseguida con el mensaje de la causa
(Spec-600 D3), sin esperas ni reintentos. Nada de la lógica del gateway va acá.
"""

import copy
import json
import logging
import time

import openai

from src.config import settings
from src.domain.exceptions import LLMRefusalError, LLMResponseError, LLMUnavailableError
from src.domain.interfaces import LLMResponse
from src.messages import message

logger = logging.getLogger(__name__)

# Modelos que razonan: rechazan `temperature` y el razonamiento sale del mismo
# `max_completion_tokens` (como el pensamiento de Claude). Se revisa al elegir el modelo (F6).
_REASONING_PREFIXES = ("gpt-5", "o1", "o3", "o4")
_NO_REASONING = ("none", "minimal")
_REASONING_MIN_MAX_TOKENS = 16000
_DEFAULT_MAX_TOKENS = 4096

# Restricciones de JSON Schema que no van en el modo estricto (quien llama valida igual).
_UNSUPPORTED_SCHEMA_KEYS = (
    "minItems",
    "maxItems",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "multipleOf",
    "default",
)


def openai_json_schema(schema: dict) -> dict:
    """Adapta un JSON Schema de Pydantic al modo estricto de OpenAI (F4).

    Cada objeto lleva `additionalProperties: false` y **todos** sus campos en `required`;
    los que eran opcionales pasan a admitir `null` (y `drop_added_nulls` los saca de la
    respuesta). No muta el esquema de quien llama.
    """
    return _strict(copy.deepcopy(schema))


def _strict(node):
    if isinstance(node, list):
        return [_strict(n) for n in node]
    if not isinstance(node, dict):
        return node
    out = {k: _strict(v) for k, v in node.items() if k not in _UNSUPPORTED_SCHEMA_KEYS}
    if out.get("type") == "object" or "properties" in out:
        props = out.get("properties", {})
        required = set(out.get("required", []))
        for name, prop in props.items():
            if name not in required and not _admits_null(prop):
                props[name] = {"anyOf": [prop, {"type": "null"}]}
        out["required"] = list(props)
        out["additionalProperties"] = False
    return out


def _admits_null(prop: dict) -> bool:
    if prop.get("type") == "null" or (
        isinstance(prop.get("type"), list) and "null" in prop["type"]
    ):
        return True
    return any(_admits_null(p) for p in prop.get("anyOf", []) if isinstance(p, dict))


def drop_added_nulls(data, schema: dict):
    """Saca los `null` de los campos que eran opcionales en el esquema original.

    El modo estricto obliga a mandar todo campo: lo que la IA no tenía para decir llega
    como `null`, y Pydantic tiene que verlo como «no vino» (usa su valor por defecto).
    """
    return _drop(data, schema, schema.get("$defs", {}))


def _resolve(node: dict, defs: dict) -> dict:
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        return defs.get(ref.removeprefix("#/$defs/"), {})
    return node


def _object_schema(node: dict, defs: dict) -> dict | None:
    node = _resolve(node, defs)
    if "properties" in node:
        return node
    for option in node.get("anyOf", []):
        found = _object_schema(option, defs)
        if found:
            return found
    return None


def _items_schema(node: dict, defs: dict) -> dict:
    node = _resolve(node, defs)
    if "items" in node:
        return node["items"]
    for option in node.get("anyOf", []):
        option = _resolve(option, defs)
        if "items" in option:
            return option["items"]
    return {}


def _drop(value, node: dict, defs: dict):
    if isinstance(value, dict):
        obj = _object_schema(node, defs)
        if obj is None:
            return value
        required = set(obj.get("required", []))
        props = obj.get("properties", {})
        return {
            k: _drop(v, props.get(k, {}), defs)
            for k, v in value.items()
            if not (v is None and k not in required)
        }
    if isinstance(value, list):
        items = _items_schema(node, defs)
        return [_drop(v, items, defs) for v in value]
    return value


def _status_cause(e: openai.APIStatusError) -> str:
    """Causa de un error HTTP de la API, para el mensaje de `LLMUnavailableError`."""
    if getattr(e, "code", None) == "insufficient_quota" or e.status_code == 402:
        # Sin saldo: OpenAI lo manda como 429 `insufficient_quota`; no es «saturada».
        return "credito"
    if e.status_code in (401, 403):
        return "clave"
    if e.status_code == 429 or e.status_code >= 500:
        return "saturada"
    return "error"


def _unavailable(cause: str, e: Exception) -> LLMUnavailableError:
    logger.error(f"[OPENAI] {cause}: {e}")
    return LLMUnavailableError(cause, message(f"llm.{cause}"), detail=str(e))


class OpenAIAdapter:
    """Adapter para la API de OpenAI (Chat Completions).

    Config por rol (perfil): `model`, `num_predict` (→ `max_completion_tokens`),
    `temperature` (solo modelos que no razonan) y `reasoning_effort` (`none` | `minimal`
    | `low` | `medium` | `high`; sin valor no se manda y el modelo usa su default).
    """

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str | None = None,
        client: openai.AsyncOpenAI | None = None,
    ):
        if client is None:
            key = api_key or settings.openai_api_key
            if not key:
                raise ValueError(
                    "OPENAI_API_KEY no configurada. "
                    "Agrégala al .env o exporta la variable de entorno."
                )
            # Sin reintentos del SDK: si no atiende, se avisa enseguida (Spec-600 D3).
            client = openai.AsyncOpenAI(api_key=key, max_retries=0)
        self._client = client
        self.default_model = default_model or settings.openai_model

    def _request(
        self,
        prompt: str,
        system_prompt: str | None,
        model: str | None,
        temperature: float | None,
        role: str | None,
        num_predict: int | None,
        response_schema: dict | None = None,
    ) -> dict:
        role_cfg = settings.role_config(role) if role else {}
        model_name = model or role_cfg.get("model") or self.default_model
        reasons = model_name.startswith(_REASONING_PREFIXES)
        effort = role_cfg.get("reasoning_effort")

        max_tokens = int(num_predict or role_cfg.get("num_predict") or _DEFAULT_MAX_TOKENS)
        if reasons and effort not in _NO_REASONING:
            # Razona: el razonamiento gasta del mismo tope; piso para no truncar el texto.
            max_tokens = max(max_tokens, _REASONING_MIN_MAX_TOKENS)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        request: dict = {
            "model": model_name,
            "messages": messages,
            "max_completion_tokens": max_tokens,
        }
        if effort:
            request["reasoning_effort"] = effort
        if temperature is not None and not reasons:
            request["temperature"] = temperature
        if response_schema:
            request["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": role or "respuesta",
                    "strict": True,
                    "schema": openai_json_schema(response_schema),
                },
            }
        return request

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        role: str | None = None,
        num_ctx: int | None = None,  # Ollama; sin efecto acá
        num_predict: int | None = None,
        response_schema: dict | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Genera texto con la API de OpenAI."""
        request = self._request(
            prompt, system_prompt, model, temperature, role, num_predict, response_schema
        )
        logger.debug(
            f"[OPENAI] model={request['model']} max={request['max_completion_tokens']} "
            f"effort={request.get('reasoning_effort')} sampling={'temperature' in request}"
        )

        t0 = time.perf_counter()
        try:
            response = await self._client.chat.completions.create(**request)
        except openai.APIStatusError as e:
            raise _unavailable(_status_cause(e), e) from e
        except openai.APIConnectionError as e:  # incluye el timeout
            raise _unavailable("sin_conexion", e) from e
        elapsed = time.perf_counter() - t0

        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else None
        output_tokens = usage.completion_tokens if usage else None
        choice = response.choices[0] if response.choices else None
        finish = choice.finish_reason if choice else None
        logger.info(
            f"[OPENAI] {request['model']} finish={finish} "
            f"in={input_tokens} out={output_tokens} elapsed={elapsed:.1f}s"
        )
        if choice is None:
            raise LLMResponseError(reason="respuesta vacía")
        if choice.message.refusal or finish == "content_filter":
            raise LLMRefusalError(finish, choice.message.refusal)
        if finish == "length":
            # Un acto truncado no se persiste.
            raise LLMResponseError(
                reason=f"respuesta truncada (max_completion_tokens={request['max_completion_tokens']})"
            )
        text = choice.message.content or ""
        if not text.strip():
            raise LLMResponseError(reason="respuesta vacía")
        if response_schema:
            text = _without_added_nulls(text, response_schema)

        return LLMResponse(
            text=text,
            elapsed_s=elapsed,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            provider="openai",
            model=response.model or request["model"],
        )

    async def close(self) -> None:
        """Cierra el cliente HTTP del SDK."""
        close = getattr(self._client, "close", None)
        if close:
            await close()


def _without_added_nulls(text: str, schema: dict) -> str:
    """El JSON sin los `null` de relleno; si no es JSON, tal cual (lo rechaza quien valida)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text
    return json.dumps(drop_added_nulls(data, schema), ensure_ascii=False)
