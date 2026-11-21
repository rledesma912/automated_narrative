import { describe, it, expect } from "vitest";
import ejs from "ejs";
import fs from "fs";
import path from "path";

/**
 * Spec-780: «Tu idea» pregunta solo lo que las autoras usan. Sin giros (S1), sin
 * «¿Qué querés que sienta quien lo escuche?» (S2) y sin «Quién lo cuenta» (S3), aunque la
 * historia los tenga guardados.
 */
const VIEWS = path.join(process.cwd(), "src/views");
const state = JSON.parse(fs.readFileSync(path.join(process.cwd(), "tests/fixtures/asistente/estado.json"), "utf8"));
const vieja = {
  ...state,
  direction: { ...state.direction, ingredient: "regla_rara", effect: "pavor", narrator: "Marta" },
};
const options = { tellings: [], criteria: [], structures: [], forms: [{ id: "regla", nombre: "Alguien rompe una regla", ayuda: "", otra: false }], hablas: [] };

const render = () =>
  ejs.renderFile(path.join(VIEWS, "asistente", "direccion.ejs"), {
    state: vieja,
    options,
    genres: [],
    estimateLabels: {},
    pasoActual: "direccion",
  });

describe("«Tu idea» más simple (Spec-780)", () => {
  it("sin giros", async () => {
    const html = await render();
    expect(html).not.toContain("data-giros");
    expect(html).not.toContain("Sorprendeme");
    expect(html).not.toContain('name="ingredient"');
  });

  it("sin «¿Qué querés que sienta quien lo escuche?»", async () => {
    const html = await render();
    expect(html).not.toContain("Qué querés que sienta");
    expect(html).not.toContain('name="effect"');
  });

  it("sin «Quién lo cuenta»: lo cuenta el protagonista", async () => {
    const html = await render();
    expect(html).toContain("¿A quién le pasa?</h3>");
    expect(html).not.toContain('name="narrator"');
    expect(html).toContain("Lo cuenta el protagonista, en primera persona.");
  });
});
