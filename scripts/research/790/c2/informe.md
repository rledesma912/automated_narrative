# Spike C2: el título a la Yael

_2026-11-23. Script: `c2_titulo.py`. Datos reales: `c2/ganchos.yaml`. Hojas en `c2/salidas/` (fuera de git): `hoja_titulos.jpg` (real | reglas | qwen | gemma) y `demo_120.jpg` (sobre las composiciones de E4, en grande y a 120 px)._

## Pregunta

Le das el gancho en texto plano. ¿Arma el título por niveles como Yael (cortes de línea, palabras chicas, acento, número gigante), y se lee a 120 px?

## Qué se corrió

- **Lo que hizo Yael:** los títulos de las 23 miniaturas de agosto a noviembre (#1–24, sin la #21, que es de dos bloques), transcriptos a ojo con sus cortes de línea, las palabras chicas y el acento.
- **Tres métodos:**
  - **reglas** (Python): las palabras de enlace van chicas; el acento es la última palabra fuerte; los cortes salen de equilibrar el ancho, dejar el acento solo en su línea y apilar de 3 a 4 líneas; el número va pegado a la primera línea.
  - **qwen2.5:14b** y **gemma3:12b** locales: cada uno recibió como ejemplos los otros 22 títulos de Yael (dejando afuera el que se evalúa) y respondió en JSON. Tardan ~2,5 s por título.
- **El dibujo:** Pillow con **Noto Serif SC ExtraBold**. La fuente se bajó de Google Fonts (OFL) y se dejó solo en ExtraBold y con los caracteres latinos (116 KB, en `assets/fonts/`). Las chicas van al 55 % y apoyadas en la línea de base, el acento naranja con brillo, el número gigante abarcando dos líneas y sombra negra difusa. El tamaño se ajusta al bloque.

## Medidas (contra lo que hizo Yael)

| | reglas | qwen2.5:14b | gemma3:12b |
|---|---|---|---|
| Usa las mismas palabras | **23/23** | 21/23 | 22/23 (cambió «TERROR» por «ERROR») |
| Cortes de línea idénticos | **8/23** | 3/23 | 7/23 |
| Misma cantidad de líneas, ±1 | **23/23** | 20/23 | 19/23 |
| Acento en la palabra de Yael (en las que tienen acento) | **10/13** | 4/12 | 8/12 |
| Palabras chicas: precisión / recall | **0,76 / 0,85** | 0,57 / 0,74 | 0,55 / 0,50 |

## Lo que se ve

1. **Las reglas ganan a las dos IA locales en todo**, y nunca cambian palabras. Las IA locales inventan acentos («DUERMAS», «LO») y ponen chicas donde no van. **Se queda con reglas.** La IA de texto del sitio solo propone el gancho, como ya dice §2.9.
2. **Los cortes que no coinciden igual son verosímiles:** «SIGUE ESTAS / REGLAS PARA / SOBREVIVIR» contra el de Yael, «SIGUE ESTAS / REGLAS / PARA / SOBREVIVIR». Ella a veces apila más alto, una palabra por línea, para llenar el bloque. Coincidir exacto en 8 de 23 es una vara dura: hay más de un corte bueno.
3. **Lo que las reglas no hacen como ella:**
   - el **doble acento** («REGLAS» y «SOBREVIVIR»);
   - el acento en el medio de la frase («AL *BOSQUE DE NOCHE», «*REPARTIR DE NOCHE»): las reglas eligen la última palabra, «NOCHE»;
   - los títulos **sin acento** de agosto. Desde septiembre lleva acento siempre, así que no es un error.
4. **Se lee a 120 px** sobre las dos composiciones de E4: el bloque blanco con el acento naranja y la sombra se distingue. Pero **sale más chico que los de Yael**: ella llena ~45 % del ancho y casi todo el alto. Ese tamaño lo fija la plantilla en C3.
5. **En la torre, el título tapa la torre:** es justo lo que resuelve C3 con lo que no se tapa.
6. **Queda para C3:** la bajada «(para NO dormir)» / «NO VER ANTES DE DORMIR», que se usa en 3 de 23; el rótulo chico; y el contraste contra lo que tiene detrás.

## Propuesta

- **Reglas** para el título, con dos ajustes que se pueden probar sin IA:
  - si la frase termina en una cola de tiempo o lugar («DE NOCHE», «EN EL CAMPO»), el acento va a la palabra fuerte de antes;
  - un tope de un acento, salvo que Yael marque dos.
- **En la tarjeta de cada miniatura**, el título se puede corregir con la misma notación, sin editor: tocar una palabra la pasa a acento, y una barra corta la línea. Esto se decide en S5 con Yael.

## Checkpoint

¿Yael reconoce sus títulos en la columna «reglas» de `hoja_titulos.jpg`? ¿Le molesta algo de la fuente o del brillo?
