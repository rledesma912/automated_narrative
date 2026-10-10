import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, it, expect } from "vitest";
import yaml from "js-yaml";
import { splitActs, ESTRUCTURAS, actosDe, estructuraPorCantidad } from "../../../src/utils/actos";

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

  it("Spec-650: un relato de 3 actos lleva los nombres del corto", () => {
    const content = "## Acto 1\n\nA.\n\n## Acto 2\n\nB.\n\n## Acto 3\n\nC.";
    expect(splitActs(content).map((a) => a.name)).toEqual(["Cómo empieza", "Qué pasa", "Cómo termina"]);
  });

  it("Spec-650: un relato de 5 actos lleva los nombres del largo", () => {
    const content = [1, 2, 3, 4, 5].map((n) => `## Acto ${n}\n\nTexto ${n}.`).join("\n\n");
    expect(splitActs(content).map((a) => a.name)).toEqual([
      "Cómo empieza",
      "Se complica",
      "El peor momento",
      "Qué hace después",
      "Cómo termina",
    ]);
  });
});

describe("Spec-650: estructuras", () => {
  it("el largo por cantidad de actos", () => {
    expect(estructuraPorCantidad(5)).toBe("largo");
    expect(estructuraPorCantidad(3)).toBe("corto");
    expect(estructuraPorCantidad(4)).toBeNull();
  });

  it("un largo desconocido es el de siempre", () => {
    expect(actosDe(undefined)).toBe(ESTRUCTURAS.largo);
    expect(actosDe("mediano")).toBe(ESTRUCTURAS.largo);
    expect(actosDe("corto")).toBe(ESTRUCTURAS.corto);
  });

  it("los nombres e intensidades son los del Core (config/llm_beats_definition.yaml)", () => {
    const file = path.resolve(__dirname, "../../../../config/llm_beats_definition.yaml");
    type Acto = { id: number; nombre_ui: string; intensity: string };
    const spec = yaml.load(readFileSync(file, "utf-8")) as {
      beats_spec: { estructuras: Record<string, { actos: Acto[] }> };
    };
    const core = spec.beats_spec.estructuras;
    expect(Object.keys(ESTRUCTURAS).sort()).toEqual(Object.keys(core).sort());
    for (const [id, data] of Object.entries(core)) {
      expect(ESTRUCTURAS[id as keyof typeof ESTRUCTURAS]).toEqual(
        data.actos.map((a) => ({ number: a.id, name: a.nombre_ui, intensity: a.intensity })),
      );
    }
  });
});
