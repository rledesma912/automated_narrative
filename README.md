
# 🧟 Guía Pro v2: Generador de Relatos con Memoria Dual (n8n + Ollama + Postgres)

## 🎯 Objetivo

Generar relatos largos (+2000 palabras) en múltiples actos sin:

* Reinicios narrativos
* Repeticiones del inicio
* Hardcoding de contexto
* Pérdida de coherencia

La solución se basa en un patrón de **Estado Narrativo Incremental con Memoria Dual**.

---

# 🏗️ Arquitectura Final Limpia

## Principios de Diseño

1. El estado vive en variables, no en el prompt.
2. La narrativa acumulada y la memoria estructurada son entidades separadas.
3. Cada iteración agrega contexto, nunca lo reemplaza.
4. El loop es puramente controlado por `acto_actual`.

---

## 📐 Diagrama Oficial (Mermaid)

```mermaid
graph TD

    %% Inicio
    A([Start]) --> B[Leer sistema.md + historia_base.md]
    B --> C[init_story_state<br/>acto_actual=1<br/>resumen_narrativo=""<br/>memoria_estructurada=""]

    %% Loop principal
    C --> D[get_current_act<br/>Extraer misión del acto]
    D --> E[LLM Narrativa<br/>Usa:<br/>- sistema<br/>- historia_base<br/>- resumen acumulado<br/>- memoria estructurada]
    
    E --> F[Persistir Acto en DB]

    F --> G[LLM Memoria Estructurada<br/>Resume SOLO hechos del acto]
    
    G --> H[update_state_and_loop<br/>- acto_actual++<br/>- acumular narrativa<br/>- acumular memoria]

    H --> I{¿acto_actual <= total_actos?}

    I -- Sí --> D
    I -- No --> J[SELECT todos los actos]
    J --> K[agregador_final<br/>Unir actos en orden]
    K --> L[Convert to File]
    L --> M([Fin])

    %% Estilos
    style E fill:#f96,stroke:#333,stroke-width:2px
    style G fill:#f96,stroke:#333,stroke-width:2px
    style F fill:#69f,stroke:#333
    style J fill:#69f,stroke:#333
```

---

# 🧠 Arquitectura de Estado Correcta

## Estructura Interna del Estado

```json
{
  "acto_actual": 2,
  "total_actos": 5,
  "resumen_narrativo_acumulado": "...texto narrativo completo hasta ahora...",
  "memoria_estructurada_acumulada": "...hechos estructurados de actos anteriores...",
  "mision_del_acto": "...extraída dinámicamente..."
}
```

---

# 🔄 Flujo Narrativo Real

## Qué recibe el LLM narrativo

```
SISTEMA
HISTORIA BASE
RESUMEN NARRATIVO ACUMULADO
MEMORIA ESTRUCTURADA
MISIÓN DEL ACTO ACTUAL
```

## Qué NO recibe

* Texto hardcodeado
* Introducciones fijas
* Resúmenes reemplazados
* Solo memoria estructurada aislada

---

# 🧩 Separación de Responsabilidades

| Componente      | Responsabilidad                      |
| --------------- | ------------------------------------ |
| LLM 1           | Generar acto narrativo               |
| DB              | Persistencia transaccional           |
| LLM 2           | Generar memoria estructurada factual |
| update_state    | Acumulación incremental              |
| IF              | Control de loop                      |
| agregador_final | Consolidación final                  |

---

# 🛑 Errores que esta arquitectura elimina

* Reinicio del Acto 1 en actos posteriores
* Reintroducción repetida de personajes
* Pérdida de continuidad emocional
* Loop infinito
* Dependencia de texto fijo

---

# 🧮 Patrón Técnico: Memoria Dual Incremental

### 1️⃣ Narrativa acumulada

Mantiene tono, progresión y tensión.

### 2️⃣ Memoria estructurada

Mantiene coherencia factual.

Ambas crecen progresivamente.

Nunca se reemplazan.

---

# ⚙️ Configuración Recomendada (RTX 3060)

Modelo:

```
llama3.1:8b
```

Parámetros:

```
num_ctx: 16384
temperature narrativa: 0.7
temperature memoria: 0.3
repeat_penalty: 1.15
```

---

# 🏁 Resultado Esperado

* Acto 2 continúa Acto 1
* Acto 3 escala conflicto
* Acto 4 profundiza tensión
* Acto 5 resuelve

Sin reinicios.

---

# 🔬 Arquitectura Mental del Sistema

Este sistema ya no es un simple loop.

Es un **motor narrativo determinístico con memoria incremental controlada**.

Puede escalar a:

* 10 actos
* 20 actos
* Historias seriadas
* Universos compartidos

Sin modificar lógica central.

---

Si quieres, el siguiente paso lógico es:

* Convertir esto en patrón reutilizable multi-historia
* O migrarlo a arquitectura orientada a eventos (más robusta)
* O agregar sistema de control de continuidad automática

Indica cuál quieres diseñar ahora.
