"""Spec-740 C1–C4: qué IA escribió cada versión, a partir del registro."""

import uuid

from src.application.services.ia_del_relato import nombre_del_modelo, resumen
from src.domain.llm_context import LLMCall

STORY, JOB = uuid.uuid4(), uuid.uuid4()


def call(role, act=None, model="gemini-3.1-flash-lite", job=JOB):
    return LLMCall(
        story_id=STORY, job_id=job, role=role, act=act, profile="p", provider="x", model=model
    )


def test_nombres_lindos_y_los_que_no_estan():
    assert nombre_del_modelo("gemini-3.1-flash-lite") == "Gemini 3.1 Flash Lite"
    assert nombre_del_modelo("gemini-3.5-flash-lite") == "Gemini 3.5 Flash Lite"  # no «Flash»
    assert nombre_del_modelo("gemini-3.5-flash") == "Gemini 3.5 Flash"
    assert nombre_del_modelo("qwen/qwen3.8-27b") == "Qwen 3.8"
    assert nombre_del_modelo("openai/gpt-oss-120b") == "GPT-OSS 120B"
    assert nombre_del_modelo("claude-sonnet-5-5") == "Claude Sonnet 5.5"
    # Un modelo nuevo: el id, sin la plataforma ni «:free».
    assert nombre_del_modelo("nvidia/nemotron-9-ultra:free") == "nemotron-9-ultra"
    assert nombre_del_modelo(None) == "?"


def test_un_solo_modelo():
    calls = [call("planificador"), *(call(r, a) for a in (1, 2, 3) for r in ("voz", "journal"))]
    r = resumen(calls, [])
    assert r["modelos"] == [{"nombre": "Gemini 3.1 Flash Lite", "actos": [1, 2, 3]}]
    assert r["por_acto"] == {
        "1": "Gemini 3.1 Flash Lite",
        "2": "Gemini 3.1 Flash Lite",
        "3": "Gemini 3.1 Flash Lite",
    }


def test_varios_modelos_en_el_orden_de_los_actos():
    calls = [
        call("voz", 1),
        call("voz", 2),
        call("voz", 3, "openai/gpt-oss-120b"),
        call("voz", 4, "qwen/qwen3.8-27b"),
        call("voz", 5, "openai/gpt-oss-120b"),
    ]
    assert resumen(calls, [])["modelos"] == [
        {"nombre": "Gemini 3.1 Flash Lite", "actos": [1, 2]},
        {"nombre": "GPT-OSS 120B", "actos": [3, 5]},
        {"nombre": "Qwen 3.8", "actos": [4]},
    ]


def test_regenerar_un_acto_cambia_solo_ese_acto():
    otro = uuid.uuid4()
    calls = [call("voz", 1), call("voz", 2), call("voz", 2, "qwen/qwen3.8-27b", job=otro)]
    r = resumen(calls, [])
    assert r["por_acto"] == {"1": "Gemini 3.1 Flash Lite", "2": "Qwen 3.8"}


def test_el_resto_del_trabajo_con_el_ultimo_modelo_de_cada_tarea():
    asistente = [
        call("consultor", model="claude-sonnet-5-5"),
        call("planificador", model="qwen/qwen3.8-27b"),
    ]
    relato = [call("planificador"), call("voz", 1), call("journal", 1, "qwen/qwen3.8-27b")]
    resto = resumen(relato, asistente)["resto"]
    assert resto == [
        {"tarea": "Las preguntas", "nombre": "Claude Sonnet 5.5"},
        {"tarea": "Armar los actos", "nombre": "Gemini 3.1 Flash Lite"},  # el del relato, después
        {"tarea": "La memoria de cada acto", "nombre": "Qwen 3.8"},
    ]


def test_sin_registro_no_dice_nada():
    assert resumen([], []) == {"modelos": [], "por_acto": {}, "resto": []}
    # Lo del asistente solo, sin la Voz del relato, tampoco (un relato viejo).
    assert resumen([], [call("consultor")]) == {"modelos": [], "por_acto": {}, "resto": []}
