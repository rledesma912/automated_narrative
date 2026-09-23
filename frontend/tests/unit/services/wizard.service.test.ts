/** Spec-440 S4: rasgos unificados con ancla YAML y narrador desde los personajes. */
import { describe, it, expect } from "vitest";
import { STEPS, getStepById, namedCharacters } from "../../../src/services/wizard.service";

const personajes = getStepById("step_config_personajes")!;

describe("ui_definitions.yaml — rasgos de personaje (§3)", () => {
  const traitFields = personajes.fields.filter((f) => /^protagonista_\d_traits$/.test(f.name));

  it("los 5 personajes comparten la misma lista (ancla YAML resuelta)", () => {
    expect(traitFields).toHaveLength(5);
    for (const f of traitFields) expect(f.options).toEqual(traitFields[0].options);
  });

  it("incluye los rasgos nuevos", () => {
    const ids = traitFields[0].options!.map((o) => o.split(":")[0].trim());
    expect(ids).toHaveLength(18);
    expect(ids).toEqual(expect.arrayContaining(["miedoso", "curioso", "impulsivo", "desconfiado"]));
  });
});

describe("storyteller_id (§5)", () => {
  it("toma las opciones de los personajes, no del YAML", () => {
    const field = STEPS.flatMap((s) => s.fields).find((f) => f.name === "storyteller_id")!;
    expect(field.source).toBe("characters");
    expect(field.options).toBeUndefined();
  });

  it("namedCharacters: solo personajes con nombre, en orden, con el nombre como label", () => {
    expect(
      namedCharacters({
        protagonista_1_name: "Irene",
        protagonista_2_name: "  ",
        protagonista_2_role: "sin nombre",
        protagonista_3_name: " Ricardo ",
      }),
    ).toEqual([
      { value: "protagonista_1", label: "Irene" },
      { value: "protagonista_3", label: "Ricardo" },
    ]);
    expect(namedCharacters({})).toEqual([]);
  });
});
