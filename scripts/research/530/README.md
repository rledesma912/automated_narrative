# Evidencia de la Spec-530 (2026-09-25)

Pruebas de investigación con `gemma3:12b` sobre «la pena del colectivo» (copia de la DB de prod).
No son parte de la app ni de CI; se corrieron desde el scratchpad de la sesión, así que las rutas
dentro de los scripts son las de ese momento.

| Script | Qué prueba | Salida |
|---|---|---|
| `probe.py` | Consultor: 7 criterios sobre la sinopsis, JSON schema, 2 corridas | (en consola; resumen en Spec-530 §1.2) |
| `probe2.py` | Igual, con contexto de objetivo vs. objetivo + teoría | (consola; §1.2) |
| `escaleta.py` | Planificador: escaleta desde sinopsis + respuestas simuladas | `escaleta_1.json`, `escaleta_2.json` |
| `build_yaml.py` + `run_pipe.py` | Pipeline real: base vs. escaleta | `salidas/relato_*.txt`, `salidas/metrics_*.json` |
| `ablation.py` | Voz: perfil del narrador actual / mínimo / opuesto | `ablation.log`, `salidas/abl_*.txt` |
