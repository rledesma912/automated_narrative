/**
 * Los actos de un relato guardado (Spec-610). Mismo formato que
 * `src/application/services/narrative_acts.py`: preámbulo opcional y un
 * `## Acto N` por acto, con los párrafos separados por una línea en blanco.
 */

/** Nombres de los actos en pantalla (Spec-580). */
export const NOMBRES_ACTOS: Record<number, string> = {
  1: "Cómo empieza",
  2: "Se complica",
  3: "El peor momento",
  4: "Qué hace después",
  5: "Cómo termina",
};

export interface ActoDelRelato {
  number: number;
  name: string;
  text: string;
}

export function splitActs(content: string): ActoDelRelato[] {
  const parts = (content || "").split(/^## Acto (\d+)[ \t]*$/m);
  const acts: ActoDelRelato[] = [];
  for (let i = 1; i < parts.length; i += 2) {
    const number = Number(parts[i]);
    acts.push({ number, name: NOMBRES_ACTOS[number] ?? `Acto ${number}`, text: (parts[i + 1] || "").trim() });
  }
  return acts;
}
