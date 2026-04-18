# SPEC 022: Saneamiento de Tests Preexistentes

## Estado

> Borrador — pendiente OK del usuario para avanzar a PLAN

## 1. Objetivo

Corregir los 3 fallos de test preexistentes identificados durante la implementación del Spec 021. Ninguno es una regresión: existían antes de los cambios de ese spec y quedaron expuestos.

---

## 2. Errores Identificados

### Error A — Desempaquetado de tupla en tests de integración

**Archivos:** `tests/integration/test_core_flow.py`

**Tests afectados:**
- `TestCoreFlowWithMocks::test_director_to_voz_flow` (línea 94)
- `TestCoreFlowWithMocks::test_full_flow_end_to_end` (línea 152)

**Síntoma:**
```
ValueError: too many values to unpack (expected 2)
```

**Causa:** `VozUseCase.execute()` firma actual:
```python
async def execute(...) -> tuple[Beat, NarrativeJournal, float]:
```
Los tests desempacan solo 2 valores:
```python
narrated_beat, journal = await voz.execute(story, beat)  # ← falla
```

**Fix:** Agregar el tercer elemento ignorado:
```python
narrated_beat, journal, _ = await voz.execute(story, beat)
```

---

### Error B — Test de AnthropicAdapter leeSettings del entorno real

**Archivo:** `tests/unit/infrastructure/test_anthropic_adapter.py`

**Test afectado:**
- `TestAnthropicAdapterInit::test_con_api_key_parametro_no_lanza` (línea 28)

**Síntoma:**
```
AssertionError: assert 'claude-3-5-sonnet-20240620' == 'claude-opus-4-7'
```

**Causa:** El test construye `AnthropicAdapter(api_key="test-key")` sin mockear `settings`. `default_model` se resuelve a `settings.anthropic_model`, que en el entorno real tiene otro valor (leído del `.env`). El test asume un valor hardcodeado en lugar de verificar el comportamiento del adapter.

**Fix:** El test debe verificar que `default_model` coincide con `settings.anthropic_model` (comportamiento real), no con un string literal hardcodeado:
```python
from src.config import settings

def test_con_api_key_parametro_no_lanza(self):
    with patch("src.infrastructure.adapters.anthropic_adapter.anthropic.AsyncAnthropic"):
        adapter = AnthropicAdapter(api_key="test-key")
        assert adapter.default_model == settings.anthropic_model
```

---

## 3. Archivos Afectados

| Archivo | Cambio |
|---|---|
| `tests/integration/test_core_flow.py` | Líneas 94 y 152: `narrated, _ = ...` → `narrated, journal, _ = ...` |
| `tests/unit/infrastructure/test_anthropic_adapter.py` | Línea 31: `assert adapter.default_model == "claude-opus-4-7"` → `assert adapter.default_model == settings.anthropic_model` |

---

## 4. Criterios de Éxito

- [ ] `pytest tests/unit/application/ tests/integration/ -q` → 0 fallos
- [ ] `pytest tests/unit/infrastructure/test_anthropic_adapter.py -q` → 0 fallos
- [ ] No se modifican firmas de producción — solo tests

---

## 5. Boundaries

| Categoría | Regla |
|---|---|
| **Always Do** | Verificar comportamiento, no valores hardcodeados del entorno |
| **Never Do** | Modificar `VozUseCase.execute()` ni `AnthropicAdapter.__init__()` — el código de producción está correcto |
