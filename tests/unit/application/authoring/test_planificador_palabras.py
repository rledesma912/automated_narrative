"""Spec-770 A: el Planificador cuenta los hechos con las palabras de la autora.

La medición de la Spec-760 (S3) mostró que la IA resumía la idea y la autora volvía a
meter su texto a mano. Este test falla si las indicaciones se pierden del prompt.
"""

from src.application.services.authoring import catalog
from src.application.services.authoring.planner import OutlinePlanner
from tests.unit.application.authoring.test_assistant_prompts_snapshot import _story


def test_el_sistema_pide_las_palabras_del_autor_y_no_inventar():
    system = OutlinePlanner(llm=None).system_prompt(_story())
    assert "Contá los hechos con las palabras del autor" in system
    assert "No lo resumas ni lo cambies por sinónimos" in system
    assert "no le sumes imágenes ni detalles tuyos" in system
    # A4: «frases simples» sigue (sobre la forma).
    assert "frases simples." in system


def test_cada_hecho_trae_su_detalle_con_el_tope_de_la_pantalla():
    prompt = OutlinePlanner(llm=None)._prompt(_story())
    assert "dos como mucho, si van seguidos" in prompt
    # El largo sigue a lo que contó el autor: con poco, no se rellena (S2: inventaba).
    assert "si lo contó en pocas palabras, una o dos oraciones" in prompt
    assert f"Nunca más de {catalog.topes()['event']} caracteres" in prompt
