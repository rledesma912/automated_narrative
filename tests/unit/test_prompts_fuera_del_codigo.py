"""Spec-620: ningún texto de prompt ni mensaje para personas escrito en Python.

Lo que lee un LLM vive en `config/prompts_generation/` (plantillas y `fragments/`); lo que
llega a la pantalla, en `config/core_messages.yaml`. Este test recorre el código con `ast` y
falla si aparece un literal de texto (más de 18 caracteres, con espacios) que no sea
docstring, argumento de un log ni una expresión regular, y que no esté en `PERMITIDOS`
(texto técnico, con su motivo) ni en `PENDIENTES` (lo que el refactor todavía no mudó).

`PENDIENTES` solo se achica: si una entrada ya no aparece en el código, el test falla para
que se la saque de la lista. Al terminar la Spec-620 queda vacía.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ("src/application", "src/infrastructure/adapters", "src/presentation/routers")
MIN_LEN = 18
_LOG_CALLS = {"debug", "info", "warning", "error", "exception", "critical"}

# (archivo, comienzo del texto) → motivo. Texto técnico: no lo lee un LLM ni una persona
# que usa el sitio.
PERMITIDOS: dict[tuple[str, str], str] = {
    (
        "src/application/services/authoring/catalog.py",
        "de el protagonista",
    ): "corrección gramatical «de el» → «del» en un replace",
    (
        "src/application/services/core_messages.py",
        "La clave {…} no es un mensaje",
    ): "error de programación (clave o fragmento inexistente)",
    (
        "src/application/services/core_messages.py",
        "Mensaje inexistente: {…}",
    ): "error de programación (clave o fragmento inexistente)",
    (
        "src/application/services/narrator_retry_generator.py",
        "Respuesta vacía después de max_retries intentos",
    ): "excepción interna (respuesta vacía del LLM)",
    (
        "src/application/services/repetition_check.py",
        "aquí allí así ahí sí mí ti qué fe café bebé mamá papá allá a",
    ): "lista de palabras de la heurística (Spec-590), no es texto",
    (
        "src/application/services/repetition_check.py",
        "es son era eran fue fueron fui hay había habían hubo he ha h",
    ): "lista de palabras de la heurística (Spec-590), no es texto",
    (
        "src/application/services/repetition_check.py",
        "me te se le les nos yo no él ella ellos ellas vos",
    ): "lista de palabras de la heurística (Spec-590), no es texto",
    (
        "src/application/services/streaming_service.py",
        "Error en generación: {…}",
    ): "registro de observabilidad (/debug)",
    (
        "src/application/services/streaming_service.py",
        "Generación completa: '{…}'",
    ): "registro de observabilidad (/debug)",
    (
        "src/application/services/template_loader.py",
        "Fragmento de prompt inexistente: {…}",
    ): "error de programación (clave o fragmento inexistente)",
    (
        "src/application/use_cases/generate_narratives_use_case.py",
        "El relato {…} no pertenece a la historia {…}",
    ): "excepción técnica (404/consistencia)",
    (
        "src/application/use_cases/generate_narratives_use_case.py",
        "La historia {…} no tiene beats para consolidar",
    ): "excepción técnica (404/consistencia)",
    (
        "src/application/use_cases/generate_narratives_use_case.py",
        "La historia {…} no tiene prosa generada en sus beats",
    ): "excepción técnica (404/consistencia)",
    (
        "src/application/use_cases/generate_narratives_use_case.py",
        "Relato generado no encontrado: {…}",
    ): "excepción técnica (404/consistencia)",
    (
        "src/application/use_cases/generate_narratives_use_case.py",
        "Story no encontrada: {…}",
    ): "excepción técnica (404/consistencia)",
    (
        "src/application/use_cases/generate_story_use_case.py",
        "✍️ Narrando acto {…}/{…}...",
    ): "progreso del CLI (consola de desarrollo)",
    (
        "src/application/use_cases/generate_story_use_case.py",
        "📐 Armando la escaleta...",
    ): "progreso del CLI (consola de desarrollo)",
    (
        "src/application/use_cases/generate_story_use_case.py",
        "📓 Memoria del acto {…}/{…}...",
    ): "progreso del CLI (consola de desarrollo)",
    (
        "src/application/use_cases/generate_story_use_case.py",
        "🔎 Revisando la escaleta...",
    ): "progreso del CLI (consola de desarrollo)",
    (
        "src/application/use_cases/regenerate_beat_voz_use_case.py",
        "Historia no encontrada: {…}",
    ): "404 técnico",
    (
        "src/infrastructure/adapters/anthropic_adapter.py",
        "ANTHROPIC_API_KEY no configurada. Agrégala al .env o exporta",
    ): "error de configuración para quien administra (arranque)",
    (
        "src/infrastructure/adapters/anthropic_adapter.py",
        "respuesta truncada (max_tokens={…})",
    ): "motivo técnico de LLMResponseError",
    (
        "src/infrastructure/adapters/gemini_cli_adapter.py",
        "Comando no encontrado: {…}",
    ): "error técnico del adapter (proveedor no usado)",
    (
        "src/infrastructure/adapters/gemini_cli_adapter.py",
        "Error de Gemini CLI: {…}",
    ): "error técnico del adapter (proveedor no usado)",
    ("src/presentation/routers/authoring_router.py", "Acto inexistente: {…}"): "404 técnico",
    ("src/presentation/routers/authoring_router.py", "Criterio desconocido: {…}"): "404 técnico",
    ("src/presentation/routers/authoring_router.py", "Historia no encontrada: {…}"): "404 técnico",
    (
        "src/presentation/routers/job_router.py",
        "El job no está en curso",
    ): "409 técnico (cancelar un job ya terminado)",
    ("src/presentation/routers/job_router.py", "Historia no encontrada: {…}"): "404 técnico",
    ("src/presentation/routers/job_router.py", "Job no encontrado: {…}"): "404 técnico",
    (
        "src/presentation/routers/job_router.py",
        "La historia no tiene un job en curso",
    ): "404 técnico (cancelar sin job)",
    (
        "src/presentation/routers/job_router.py",
        "Relato no encontrado para esta historia",
    ): "404 técnico",
    (
        "src/presentation/routers/job_router.py",
        "regenerate_voz requiere beat y narrative_id",
    ): "422 técnico (contrato del API)",
    ("src/presentation/routers/narrative_router.py", "Error al generar narrativa"): "500 técnico",
    ("src/presentation/routers/narrative_router.py", "ID de narrativa inválido"): "422 técnico",
    ("src/presentation/routers/narrative_router.py", "ID de plantilla inválido"): "422 técnico",
    (
        "src/presentation/routers/narrative_router.py",
        "Narrativa eliminada",
    ): "respuesta del API (la UI no la muestra)",
    ("src/presentation/routers/narrative_router.py", "Narrativa no encontrada"): "404 técnico",
    (
        "src/presentation/routers/narrative_router.py",
        'attachment; filename="{…}"',
    ): "encabezado HTTP",
    ("src/presentation/routers/narrative_router.py", "text/markdown; charset=utf-8"): "tipo MIME",
    (
        "src/presentation/routers/story_router.py",
        "Historia '{…}' eliminada de DB",
    ): "respuesta del API (la UI no la muestra)",
    (
        "src/presentation/routers/story_router.py",
        "Historia '{…}' guardada como {…}",
    ): "respuesta del API (la UI no la muestra)",
    ("src/presentation/routers/story_router.py", "Historia no encontrada: {…}"): "404 técnico",
    (
        "src/presentation/routers/story_router.py",
        "Limpieza completa para regeneración — story_id={…}",
    ): "respuesta del API (la UI no la muestra)",
    (
        "src/presentation/routers/story_router.py",
        "Status '{…}' no permitido. Válidos: {…}",
    ): "422 técnico",
    (
        "src/presentation/routers/stream_router.py",
        "Cargando beats históricos...",
    ): "evento técnico del stream de solo lectura",
    ("src/presentation/routers/stream_router.py", "Historia no encontrada: {…}"): "404 técnico",
    (
        "src/presentation/routers/stream_router.py",
        "cli-based (no ping available)",
    ): "estado técnico de /health",
}

# Archivos enteros fuera del alcance, con su motivo.
ARCHIVOS_PERMITIDOS = {
    "src/infrastructure/adapters/mock_llm_adapter.py": "respuestas del mock (tests, --mock)",
    "src/infrastructure/adapters/mock_structured.py": "respuestas del mock (tests, --mock)",
}

# (archivo, comienzo del texto): lo que falta mudar, por slice de la Spec-620.
PENDIENTES: set[tuple[str, str]] = {
    # S2 — el asistente → fragments/asistente
    (
        "src/application/services/authoring/context.py",
        "(DECIDIDO POR EL AUTOR: no se discute ni se cambia)",
    ),
    (
        "src/application/services/authoring/context.py",
        "(el autor todavía no tomó decisiones en el taller)",
    ),
    ("src/application/services/authoring/context.py", "(va en el acto {…})"),
    (
        "src/application/services/authoring/context.py",
        "- [{…}] {…}. Pregunta: «{…}» → Respuesta: {…}",
    ),
    (
        "src/application/services/authoring/context.py",
        "- [{…}] {…}: {…} (DECIDIDO POR EL AUTOR: no se discute)",
    ),
    (
        "src/application/services/authoring/context.py",
        "CÓMO TIENE QUE PEGAR (el efecto que busca el autor: {…}): {…",
    ),
    ("src/application/services/authoring/context.py", "Cómo lo cuenta: {…}"),
    ("src/application/services/authoring/context.py", "Cómo termina: {…}{…}"),
    (
        "src/application/services/authoring/context.py",
        "EFECTO QUE BUSCA EL AUTOR: {…}. La escaleta tiene que cumpli",
    ),
    ("src/application/services/authoring/context.py", "Efecto que busca el autor: {…}"),
    (
        "src/application/services/authoring/context.py",
        "Estamos ayudando a un autor a preparar un cuento de terror q",
    ),
    ("src/application/services/authoring/context.py", "Quién lo cuenta: {…}"),
    ("src/application/services/authoring/context.py", "Tipo de horror: {…}"),
    (
        "src/application/services/authoring/planner.py",
        "; acá el protagonista descubre o confiesa la historia secret",
    ),
    (
        "src/application/services/authoring/planner.py",
        "LO QUE EL AUTOR ESCRIBIÓ PARA CADA ACTO (respetalo: es su hi",
    ),
    (
        "src/application/services/authoring/planner.py",
        "PROBLEMAS QUE MARCÓ LA REVISIÓN EN LA ESCALETA ANTERIOR (res",
    ),
    ("src/application/services/authoring/planner.py", "actos sin hechos: {…}"),
    (
        "src/application/services/authoring/planner.py",
        "cerrar la historia con el final que decidió el autor",
    ),
    (
        "src/application/services/authoring/planner.py",
        "la escaleta tiene que tener los actos 1 a 5 (llegaron {…})",
    ),
    ("src/application/services/authoring/planner.py", "{…}. {…} (intensidad {…}): {…}"),
    ("src/application/services/authoring/verifier.py", "(se revela en el acto {…})"),
    ("src/application/services/authoring/verifier.py", "Todavía no se cuenta: {…}{…}"),
    # S3 — mensajes para personas → config/core_messages.yaml
    (
        "src/application/services/authoring/verifier.py",
        "El acto termina igual que empieza: ¿qué le cambia a {…}?",
    ),
    (
        "src/application/services/authoring/verifier.py",
        "El secreto de este acto no se descubre en ningún acto poster",
    ),
    (
        "src/application/services/authoring/verifier.py",
        "En este acto no pasa nada todavía: ¿qué pasa acá?",
    ),
    (
        "src/application/services/authoring/verifier.py",
        "No dice cómo se llega acá desde el acto anterior: completá «",
    ),
    (
        "src/application/services/authoring/verifier.py",
        "{…} aparecen acá y no vuelven en ningún acto posterior: ¿los",
    ),
    (
        "src/application/services/authoring/verifier.py",
        "«{…}» aparece acá y no vuelve en ningún acto posterior: ¿lo ",
    ),
    (
        "src/application/services/authoring/verifier.py",
        "«{…}» aparece en este acto pero no está entre los personajes",
    ),
    (
        "src/application/services/authoring/workshop_rules.py",
        "(Es la última vuelta de preguntas: el máximo es {…}.)",
    ),
    (
        "src/application/services/authoring/workshop_rules.py",
        "El criterio {…} no tiene opciones para elegir",
    ),
    (
        "src/application/services/authoring/workshop_rules.py",
        "La IA no encontró preguntas nuevas: {…} sin responder de ant",
    ),
    (
        "src/application/services/authoring/workshop_rules.py",
        "La IA no tiene más preguntas. Ya podés armar los actos.",
    ),
    (
        "src/application/services/authoring/workshop_rules.py",
        "Te queda{…} {…} {…}. Podés responder, pedirle a la IA que te",
    ),
    (
        "src/application/services/authoring/workshop_rules.py",
        "Tu historia ya tiene todo lo que hace falta. Ya podés armar ",
    ),
    (
        "src/application/services/authoring/workshop_rules.py",
        "Ya van {…} vueltas de preguntas, que es el máximo. Podés res",
    ),
    ("src/application/services/authoring/workshop_rules.py", "quedan {…} preguntas"),
    ("src/application/services/job_manager.py", "La historia ya tiene un job activo: {…}"),
    ("src/application/services/job_manager.py", "error en el pipeline"),
    ("src/application/services/streaming_service.py", "Escribiendo el acto {beat} de {total}..."),
    ("src/application/services/streaming_service.py", "Juntando el relato..."),
    ("src/application/services/streaming_service.py", "Leyendo tu historia…"),
    ("src/application/services/streaming_service.py", "Repasando lo que pasó en el acto {beat}..."),
    ("src/application/services/streaming_service.py", "Revisando los actos…"),
    ("src/application/use_cases/create_story.py", "Dato inválido en {…} ({…}): {…}"),
    (
        "src/application/use_cases/create_story.py",
        "Entidad {…}: la naturaleza '{…}' no corresponde {…}",
    ),
    ("src/application/use_cases/create_story.py", "La escaleta repite un número de acto"),
    ("src/application/use_cases/create_story.py", "Tipo de personaje inválido para «{…}»: {…}"),
    (
        "src/application/use_cases/create_story.py",
        "Una historia admite hasta {…} entidades (llegaron {…})",
    ),
    ("src/application/use_cases/create_story.py", "a ninguna del catálogo"),
    ("src/application/use_cases/create_story.py", "escaleta, elemento {…}"),
    ("src/application/use_cases/create_story.py", "taller, elemento {…}"),
    ("src/application/use_cases/create_story.py", "{…} no es válido (opciones: {…})"),
    ("src/application/use_cases/create_story.py", "{…} supera los {…} caracteres"),
    ("src/application/use_cases/create_story.py", "«Nivel de revelación»"),
    (
        "src/application/use_cases/regenerate_beat_voz_use_case.py",
        "Acto {…} no encontrado o no narrado aún",
    ),
    (
        "src/application/use_cases/regenerate_beat_voz_use_case.py",
        "La historia no tiene escaleta: generala de nuevo para poder ",
    ),
    (
        "src/infrastructure/adapters/anthropic_adapter.py",
        "La IA que escribe el relato está saturada. Probá de nuevo en",
    ),
    (
        "src/infrastructure/adapters/anthropic_adapter.py",
        "La IA que escribe el relato no acepta la clave (venció o no ",
    ),
    (
        "src/infrastructure/adapters/anthropic_adapter.py",
        "La IA que escribe el relato respondió con un error. Probá de",
    ),
    (
        "src/infrastructure/adapters/anthropic_adapter.py",
        "La IA que escribe el relato se quedó sin crédito. Avisá a qu",
    ),
    (
        "src/infrastructure/adapters/anthropic_adapter.py",
        "No se pudo hablar con la IA que escribe el relato (sin conex",
    ),
    ("src/presentation/routers/authoring_router.py", "(todavía sin contar)"),
    ("src/presentation/routers/authoring_router.py", "Datos rechazados: {…}"),
    (
        "src/presentation/routers/authoring_router.py",
        "La IA está trabajando en esta historia: esperá a que termine",
    ),
    ("src/presentation/routers/authoring_router.py", "La respuesta está vacía"),
    ("src/presentation/routers/authoring_router.py", "Primera persona en pasado. Narrador: {…}."),
    (
        "src/presentation/routers/authoring_router.py",
        "Todavía no hay preguntas: apretá «Que la IA me pregunte».",
    ),
    ("src/presentation/routers/job_router.py", "El acto {…} no está narrado"),
    ("src/presentation/routers/job_router.py", "Falta contar de qué trata la historia (Dirección)"),
    ("src/presentation/routers/job_router.py", "La historia ya tiene una generación en curso"),
    ("src/presentation/routers/job_router.py", "No hay escaleta para revisar"),
    (
        "src/presentation/routers/story_router.py",
        "Datos rechazados por la base (género/subgénero o naturaleza ",
    ),
    (
        "src/presentation/routers/story_router.py",
        "Hay una generación en curso; esperá a que termine para edita",
    ),
    (
        "src/presentation/routers/stream_router.py",
        "No hay una generación en curso para esta historia",
    ),
}


def _texts(path: Path) -> list[str]:
    """Literales de texto del archivo, sin docstrings, logs ni regex (`{…}` = interpolación)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
            and body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
        ):
            skip.add(id(body[0].value))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            is_log = node.func.attr in _LOG_CALLS and isinstance(node.func.value, ast.Name)
            is_regex = isinstance(node.func.value, ast.Name) and node.func.value.id == "re"
            if is_log or is_regex:
                skip.update(id(n) for n in ast.walk(node))
    found = []
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.JoinedStr):
            skip.update(id(v) for v in node.values)
            text = "".join(v.value if isinstance(v, ast.Constant) else "{…}" for v in node.values)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
        else:
            continue
        if len(text) > MIN_LEN and " " in text.strip():
            found.append(text)
    return found


def findings() -> set[tuple[str, str]]:
    out = set()
    for scope in SCOPE:
        for path in sorted((ROOT / scope).rglob("*.py")):
            rel = str(path.relative_to(ROOT))
            if rel in ARCHIVOS_PERMITIDOS:
                continue
            out.update((rel, " ".join(text.split())[:60]) for text in _texts(path))
    return out


def test_no_hay_textos_de_prompt_ni_mensajes_en_el_codigo():
    unexpected = sorted(findings() - set(PERMITIDOS) - PENDIENTES)
    assert not unexpected, (
        "Texto de prompt o mensaje en Python: va en config/prompts_generation/fragments/ "
        "(LLM) o en config/core_messages.yaml (pantalla). Si es técnico, sumalo a "
        "PERMITIDOS con su motivo.\n" + "\n".join(f"  {f}: {t!r}" for f, t in unexpected)
    )


def test_pendientes_solo_se_achica():
    done = sorted(PENDIENTES - findings())
    assert not done, "Ya no están en el código: sacalos de PENDIENTES.\n" + "\n".join(
        f"  {f}: {t!r}" for f, t in done
    )


def test_permitidos_existen():
    stale = sorted(set(PERMITIDOS) - findings())
    assert not stale, "Ya no están en el código: sacalos de PERMITIDOS.\n" + "\n".join(
        f"  {f}: {t!r}" for f, t in stale
    )


def test_detecta_textos_y_respeta_docstrings_logs_y_regex(tmp_path):
    code = tmp_path / "x.py"
    code.write_text(
        '"""Docstring del módulo, que no cuenta."""\n'
        "import logging, re\n"
        "logger = logging.getLogger(__name__)\n"
        "PATRON = re.compile(r'una expresión regular larga')\n"
        "def f(n):\n"
        '    """Docstring de la función."""\n'
        "    logger.info(f'un log con {n} cosas adentro')\n"
        "    return f'CÓMO ESTÁ {n} AHORA (no lo contradigas)'\n",
        encoding="utf-8",
    )
    assert _texts(code) == ["CÓMO ESTÁ {…} AHORA (no lo contradigas)"]
