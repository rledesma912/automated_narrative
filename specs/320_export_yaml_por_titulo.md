# Spec-320: Workflow CLI — Exportar historia a YAML y regenerar

## Metadata

| Campo | Valor |
|-------|-------|
| **Status** | ✅ COMPLETADO |
| **Tipo** | Feature (Workflow) |
| **Slice base** | S0 |
| **Fecha** | 2026-05-07 |
| **Owner** | Backend / CLI |
| **Spec relacionado** | 217 (export-yaml), 302 (yaml loader), 220 (formato YAML), 120 (CLI) |

---

## 1. Objetivo

Documentar el workflow de dos pasos por terminal:
1. **Exportar**: Dado un `story_id` (UUID), generar un documento YAML canónico
2. **Regenerar**: Usar ese YAML con `generate --input` para recrear la historia

## 2. Estado

El código necesario **ya existe** (Spec-302). No se requirió desarrollo nuevo.

### Componentes disponibles

| Comando | Descripción |
|---------|-------------|
| `make list` | Lista historias con UUID y título |
| `python -m src export-yaml <UUID>` | Exporta a YAML canónico (default: input_stories/<slug>.yaml) |
| `python -m src export-yaml <UUID> --output <path>` | Exporta a path específico |
| `python -m src generate --input <yaml>` | Genera historia desde YAML canónico |
| `./scripts/bash/run_export.sh <UUID> [output]` | Script helper para exportar |
| `make export ARG=<UUID>` | Make target que usa el script |
| `make export-yaml ARG=<UUID> OUTPUT=<path>` | Make target con output específico |

## 3. Slices (todos completados)

### Slice S0 — Baseline ✅

- [x] S0-T1: `make list` mostrar historias disponibles
- [x] S0-T2: `python -m src export-yaml --help` muestra ayuda
- [x] S0-T3: `python -m src generate --input --help` muestra ayuda
- [x] S0-T4: Snapshot de tests: `pytest tests -v` verde
- [x] S0-T5: YamlStoryLoader existe en `src/infrastructure/loaders/`

### Slice S1 — Exportar historia a YAML ✅

- [x] S1-T1: `export-yaml` funciona con UUIDs reales
- [x] S1-T2: Genera archivo YAML en `input_stories/`
- [x] S1-T3: YAML contiene title, protagonista, sinopsis, etc.
- [x] S1-T4: UUID inválido lanza error claro

### Slice S2 — Cargar YAML con YamlStoryLoader ✅

- [x] S2-T1: YamlStoryLoader puede parsear el YAML exportado
- [x] S2-T2: DTO resultante tiene campos no vacíos

### Slice S3 — Regenerar desde YAML ✅

- [x] S3-T1: `generate --input <yaml>` recrea la historia
- [x] S3-T2: Historia se crea en DB con metadata correcta

### Slice S4 — Make targets y script helper ✅

- [x] S4-T1: `make export` target agregado
- [x] S4-T2: `make export-yaml` target agregado
- [x] S4-T3: `scripts/bash/run_export.sh` actualizado para usar export-yaml

## 4. Comandos de uso

```bash
# 1. Listar historias disponibles
make list

# 2. Exportar a YAML (path automático)
make export ARG=feba722b-dc89-4009-9764-98ac4207696b

# 3. Exportar a YAML con path específico
make export-yaml ARG=feba722b-dc89-4009-9764-98ac4207696b OUTPUT=input_stories/barco_fantasma.yaml

# 4. Regenerar desde YAML
python -m src generate --input input_stories/barco_fantasma.yaml --mock

# Alternativa: usar el script directamente
./scripts/bash/run_export.sh feba722b-dc89-4009-9764-98ac4207696b input_stories/barco_fantasma.yaml
```

## 5. Resultado

✅ Workflow documentado y verificado. El sistema tiene todas las piezas necesarias para:
- Exportar cualquier historia de la DB a YAML canónico
- Regenerar una historia desde cualquier YAML canónico válido

## 6. Breaking Changes

Ninguno. Solo se agregaron targets al Makefile y se actualizó el script shell.