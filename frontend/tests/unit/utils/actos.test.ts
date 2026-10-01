import { describe, it, expect } from "vitest";
import { splitActs, NOMBRES_ACTOS } from "../../../src/utils/actos";

/** Spec-610 T1.4: los actos de un relato guardado (mismo formato que narrative_acts.py). */
describe("splitActs", () => {
  it("parte por «## Acto N» con su nombre de pantalla y sin el preámbulo", () => {
    const content = "# Título\n\n## Acto 1\n\nUno.\n\nDos.\n\n## Acto 2\n\nTres.\n";
    expect(splitActs(content)).toEqual([
      { number: 1, name: "Cómo empieza", text: "Uno.\n\nDos." },
      { number: 2, name: "Se complica", text: "Tres." },
    ]);
  });

  it("sin actos devuelve una lista vacía", () => {
    expect(splitActs("Un texto suelto.")).toEqual([]);
    expect(splitActs("")).toEqual([]);
  });

  it("los cinco nombres de los actos", () => {
    expect(Object.values(NOMBRES_ACTOS)).toEqual([
      "Cómo empieza",
      "Se complica",
      "El peor momento",
      "Qué hace después",
      "Cómo termina",
    ]);
  });
});
