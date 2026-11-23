# Spike C1: el catálogo de Yael

_2026-11-23. Script: `c1_catalogo.py`. Anotación: `c1/anotacion.yaml`. Las hojas por plantilla están en `c1/salidas/` (fuera de git)._

## Pregunta

¿Se pueden medir las miniaturas de Yael y sacar sus plantillas con rangos, usando las **recientes** como patrón (D19)?

## Qué se corrió

- **Las 124 miniaturas del canal** se bajaron con sus fechas. Las «recientes» son las **36 publicadas desde junio de 2026**: entre la #36 (19/6) y la #37 (22/5) hay un mes sin videos, y ese hueco hace de corte natural.
- **Texto:** máscaras de color (blanco y rojo/naranja) → Tesseract `spa` → palabras con su caja, agrupadas en líneas y en el bloque del título. El modelo `spa` (tessdata_best) quedó en `insumos/tessdata/`, sin `sudo`.
- **Figura:** BiRefNet (el de E2) sobre la miniatura con el texto tapado → la caja de la figura. Fueron 124 llamadas de ~0,8 s.
- **Etiquetas:** reglas legibles que asignan la plantilla (lado del título, dos alturas, tamaño de la figura).

## Resultado: la medición automática **no pasa** el criterio (más de 1 error cada 5)

- **El texto anda razonable.** En la mayoría de los casos la caja del título cae bien. Pero el OCR lee mal el texto («AMÁS VIA SAL GAS») y se le escapan palabras de acento con contorno, y algunos pedazos de la figura entran como «palabras». Para medir **dónde** está el título alcanza; para leer el gancho tal cual, no (eso es C2).
- **La figura no anda.** En una miniatura terminada, BiRefNet marca como «objeto principal» la escena entera, la calabaza o una mano, y no la entidad. Pasó en 8 de 36 de las recientes, como mínimo.
- **La regla de «dos alturas» da falsos positivos** por esos pedazos sueltos: clasificó 16 de 36 como D y en realidad son 12.

Por eso **el catálogo se armó a ojo**, sobre las hojas de contacto y con las cajas del OCR como ayuda (`c1/anotacion.yaml`). Son 36 miniaturas y llevó minutos. La spec ya preveía que se revisara a mano. Si en el futuro se quiere volver a medir solo, con miniaturas nuevas, el candidato es un modelo de visión que ubique cosas (Qwen2.5-VL 7B, Apache-2.0). Queda anotado, sin probar.

## Lo que muestran las 36 recientes

| Período | Plantillas | Figura | Acento |
|---|---|---|---|
| **Sep–nov** (#1–15) | **A 9**, C 3, B 2, D 1 | **a la derecha 9 de 15**, grande o primer plano 11 de 15 | **naranja 9**, rojo 4 |
| Agosto (#16–24) | **A 8**, D 1 | a la derecha 7 de 9, todas grandes | sin acento 6, rojo 3 |
| Jun–jul (#25–36) | **D 10**, A 2 | media o chica 9 de 12 | rojo 9 |

1. **Yael cambió de forma de componer en agosto.** En junio y julio el título iba en dos bloques (el tema arriba y el gancho abajo) con la figura chica. Desde agosto, **la figura es grande de un lado y el título va en un solo bloque del otro (plantilla A)**.
2. **Hoy la figura va a la derecha y el título a la izquierda** en 16 de 24 (agosto–noviembre). Contradice lo que se vio en §1.7 con las 8 viejas, donde la figura iba a la izquierda.
3. **El título:** 3 o 4 líneas en un bloque de ~40–50 % del ancho, apoyado arriba, en el medio o abajo según dónde quede lugar. El número gigante («3», «5») aparece en 6 de 24, y una **bajada chica** abajo («para NO dormir», «NO VER ANTES DE DORMIR») en 3.
4. **El acento es naranja** en las más nuevas (desde septiembre). Coincide con D-Q14.
5. **Primer plano (C)** de una cara, una mano o una persona: 3 de 15 en las más nuevas. **Lugar o vehículo que manda (B)**: 2 de 15. Es la torre (#2), justo uno de los casos de prueba.

## Borrador del catálogo (para `config/miniatura/catalogo.yaml`)

| Plantilla | Figura | Título | Peso (las 24 de ago–nov) |
|---|---|---|---|
| `A_der` | derecha, 75–100 % del alto (puede ir cortada abajo), centro en x 0,62–0,75 | izquierda, 3–4 líneas, ancho 0,40–0,50; apoyado donde no tape lo importante | 13 |
| `A_izq` | el espejo (la coneja, #5) | derecha | 4 |
| `C_primer_plano` | cara, mano o torso ocupando su mitad, cortada por el borde | el lado opuesto, al medio | 3 |
| `B_lugar` | figura media o chica, al centro, con el lugar (torre, camión) | un lado, todo el alto, con bajada | 2 |
| `D_dos_bloques` | media o chica | el tema arriba y el gancho abajo, en el lado opuesto | 1 (era la de jun–jul) |

**El compositor** ofrecería 4 de estas según el caso. Con una entidad alta y un lugar con algo importante (la torre): `B_lugar`, `A_der`, `A_izq` y `C_primer_plano`. Con una figura humana (la coneja): `A_izq`, `A_der`, `C_primer_plano` y `B_lugar`.

## Checkpoint con Yael

1. ¿Estas son sus plantillas de hoy? ¿Le falta alguna?
2. ¿`D_dos_bloques` (la de junio y julio) queda afuera, o la ofrecemos de vez en cuando?
3. ¿La figura a la derecha es una elección, o salió así?
