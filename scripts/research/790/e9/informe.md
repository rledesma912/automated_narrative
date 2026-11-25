# Spike E9: la cadena por Python

_2026-11-23. Script: `e9_cadena.py`. Salidas en `e9/salidas/` (fuera de git)._

## Pregunta

Encadenadas en un solo script, ¿las partes andan juntas, entran en la VRAM y en cuánto tiempo?

## Qué se corrió

Una historia (la coneja), de los bocetos a las 4 opciones, con la GPU libre (audiogen sin cargar):

1. personaje: Qwen en color → BiRefNet → recorte;
2. escenario: Qwen → curva → Z-Image 0,45;
3. las 4 plantillas de C3, sin título, con el fundido de E4;
4. el tono del lugar (C5c).

`nvidia-smi` midió la placa en paralelo cada 0,5 s.

## Medidas

| Paso | Tiempo |
|---|---|
| Piezas (personaje + escenario, con la carga de los modelos) | 298 s |
| 4 composiciones con fundido | 378 s (el primero 114 s, cargando el modelo; después ~82 s cada uno) |
| Color | 0,9 s |
| **Total** | **677 s ≈ 11 min** |
| VRAM pico de la placa | **11,5 GB de 12** |

## Conclusiones

- **Anda de punta a punta y sin errores de memoria.** ComfyUI cambia solo de Qwen a Z-Image y a BiRefNet.
- **Con 11,5 GB de pico no hay lugar para audiogen al mismo tiempo.** El arnés libera la memoria, mira cuánta VRAM queda y, si no alcanza, espera (etapa `esperando_gpu`, hasta 30 min), como pide D10. No se corrió con audiogen generando: lo vamos a ver en el uso real.
- **El tiempo estimado inicial de `thumbnail_build` queda en 680 s.** Una segunda tanda sin cambios en los bocetos reusa las piezas y tarda ~6 min.
