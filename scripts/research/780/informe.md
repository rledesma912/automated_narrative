# Spec-780 S5: sin efecto y las dos formas de contarlo

**Fecha:** 2026-11-21 · **Perfil:** `openai-sol` (GPT-5.6 Sol) · **Costo:** US$ 0,354 (tope US$ 0,40)

## 1. Armar los actos sin efecto (`resultados_sin_efecto.json`)

Dos historias Media de prod con efectos de receta fuerte, armadas de nuevo sin efecto sobre una copia de la base:

| Historia (efecto guardado) | En prod: avisos · final en el último acto | Sin efecto: avisos · final |
|---|---|---|
| «la niña olvidada» (revelación) | 7 · sí | 7 · sí |
| «el engaño del diablo» (susto) | 9 · **no** | **1** · sí |

- Los avisos que quedan son de personajes, de cosas sembradas y de algo que se adelanta un acto. **Ninguno tiene que ver con el efecto.**
- Los actos de prod son de octubre (otro modelo y el prompt anterior a la Spec-770): la comparación es una referencia, no aísla solo el efecto.
- La estructura no empeora: el final queda en el último acto en las dos, de 3 a 5 hechos por acto.

## 2. «Culpable» con las dos formas, sobre los mismos actos (`resultados_como_lo_cuenta.json`)

| | Como a un amigo | Como si lo escribieras |
|---|---|---|
| Palabras | 1.133 | 1.184 |
| Palabras por oración | 15,1 | 16,4 |
| Comparaciones cada 1.000 palabras | 1,8 | 1,7 |
| Marcas orales cada 1.000 palabras | 0,9 | **0** |
| Clichés · diálogo | 0 · 0 | 0 · 0 |
| Costo | US$ 0,107 | US$ 0,106 |

**Leídas, se distinguen.**
- **«Como a un amigo»** suena a charla: «una culpa que, la verdad, me había ganado solo», «Una crueldad, sí.», «ni una mísera rareza», «puro cuento».
- **«Como si lo escribieras»** es más cuidada y descriptiva, con vocabulario más escrito («desestimé», «permanecí», «percibir»): «Por la forma redondeada del techo y los guardabarros se parecía a un Volkswagen Escarabajo», «con una presión seca detrás de los ojos», «del otro lado del vidrio no llegaba ningún sonido».
- **No exagera:** cero clichés, las mismas comparaciones y nada de imágenes rebuscadas.
- **Lo que no llega:** «narrativa más compleja». Las oraciones son apenas más largas (16,4 contra 15,1 palabras). Si Yael la quiere más literaria, el ajuste es el bloque `voz/contar/escrito.md` (por ejemplo, pedir más oraciones largas con subordinadas). No quedó presupuesto para probarlo en esta medición.
