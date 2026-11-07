/**
 * Los actos de un relato (Spec-610, Spec-650). Mismo formato que
 * `src/application/services/narrative_acts.py`: preámbulo opcional y un
 * `## Acto N` por acto, con los párrafos separados por una línea en blanco.
 *
 * Spec-650/750: hay tres largos (corto, medio, largo); la larga tiene los actos de la media. Esta es la única fuente de los nombres de los actos en
 * el front (la imagen de la UI no trae `config/`); un test los compara con
 * `nombre_ui` e `intensity` de `config/llm_beats_definition.yaml`.
 */

export type Estructura = "medio" | "corto" | "largo";

export interface ActoDeLaEstructura {
  number: number;
  name: string; // Spec-580: el nombre en pantalla
  intensity: string;
}

export const ESTRUCTURAS: Record<Estructura, ActoDeLaEstructura[]> = {
  medio: [
    { number: 1, name: "Cómo empieza", intensity: "baja" },
    { number: 2, name: "Se complica", intensity: "media" },
    { number: 3, name: "El peor momento", intensity: "alta" },
    { number: 4, name: "Qué hace después", intensity: "media-alta" },
    { number: 5, name: "Cómo termina", intensity: "baja" },
  ],
  largo: [
    { number: 1, name: "Cómo empieza", intensity: "baja" },
    { number: 2, name: "Se complica", intensity: "media" },
    { number: 3, name: "El peor momento", intensity: "alta" },
    { number: 4, name: "Qué hace después", intensity: "media-alta" },
    { number: 5, name: "Cómo termina", intensity: "baja" },
  ],
  corto: [
    { number: 1, name: "Cómo empieza", intensity: "baja" },
    { number: 2, name: "Qué pasa", intensity: "alta" },
    { number: 3, name: "Cómo termina", intensity: "baja" },
  ],
};

/** Los actos de un largo (uno desconocido es el de siempre, la media). */
export function actosDe(estructura: string | undefined): ActoDeLaEstructura[] {
  return ESTRUCTURAS[estructura as Estructura] ?? ESTRUCTURAS.medio;
}

/**
 * El largo de un relato ya escrito, por cuántos actos tiene: una versión puede ser de
 * cuando la historia tenía otro largo (Spec-650 D11), así que no sale de la historia.
 */
export function estructuraPorCantidad(cantidad: number): Estructura | null {
  const found = (Object.keys(ESTRUCTURAS) as Estructura[]).find((e) => ESTRUCTURAS[e].length === cantidad);
  return found ?? null;
}

/** Spec-650: un estado del asistente sin el largo (Core viejo, dobles de prueba) es la media. */
export function conLargo<T extends { structure?: string; structure_acts?: ActoDeLaEstructura[] }>(
  state: T,
): T & { structure: string; structure_acts: ActoDeLaEstructura[] } {
  const structure = state.structure || "medio";
  const acts = state.structure_acts?.length ? state.structure_acts : actosDe(structure);
  return { ...state, structure, structure_acts: acts };
}

export interface ActoDelRelato {
  number: number;
  name: string;
  text: string;
}

export function splitActs(content: string): ActoDelRelato[] {
  const parts = (content || "").split(/^## Acto (\d+)[ \t]*$/m);
  const raw: { number: number; text: string }[] = [];
  for (let i = 1; i < parts.length; i += 2) {
    raw.push({ number: Number(parts[i]), text: (parts[i + 1] || "").trim() });
  }
  // Una cantidad que no es de ningún largo (no debería pasar) conserva los nombres de siempre.
  const nombres = ESTRUCTURAS[estructuraPorCantidad(raw.length) ?? "medio"];
  return raw.map((a) => ({
    ...a,
    name: nombres.find((n) => n.number === a.number)?.name ?? `Acto ${a.number}`,
  }));
}

/**
 * Spec-650 D11: la versión se escribió con otro largo que el de la historia ahora. Se lee,
 * se corrige y se descarga, pero no se regenera por actos (el Core lo rechaza).
 * Spec-750: la media y la larga tienen los mismos actos: cuenta el largo guardado de la versión
 * (`delaVersion`, lo manda el Core); sin él, la cantidad de actos.
 */
export function deOtroLargo(content: string, estructura: string | undefined, delaVersion?: string): boolean {
  const cantidad = splitActs(content).length;
  if (cantidad === 0) return false;
  if (delaVersion) return delaVersion !== (estructura || "medio");
  return cantidad !== actosDe(estructura).length;
}
