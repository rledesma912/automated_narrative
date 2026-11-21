"""Spec-760 A4: un 422 por un texto o una lista de más responde en el tono del sitio.

El asistente muestra `detail` tal cual cuando es texto (`asistente.js`, `errorText`). Los
demás errores de validación siguen con la respuesta de siempre de FastAPI.
"""

from fastapi import Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.messages import message

_DE_MAS = {"string_too_long", "too_long"}


def miles(n: int) -> str:
    """21300 → «21.300», como se escriben los números en la pantalla."""
    return f"{n:,}".replace(",", ".")


def texto_de_mas(error: dict) -> str:
    """El mensaje para un error de Pydantic por un texto o una lista de más."""
    maximo = miles(error["ctx"]["max_length"])
    if error["type"] == "string_too_long":
        return message("validacion.texto_largo", largo=miles(len(error["input"])), maximo=maximo)
    return message(
        "validacion.lista_larga", maximo=maximo, llegaron=miles(error["ctx"]["actual_length"])
    )


async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    if errors and all(e.get("type") in _DE_MAS for e in errors):
        return JSONResponse(status_code=422, content={"detail": texto_de_mas(errors[0])})
    return await request_validation_exception_handler(request, exc)
