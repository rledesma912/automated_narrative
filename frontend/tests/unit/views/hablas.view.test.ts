import { describe, it, expect } from "vitest";
import ejs from "ejs";
import fs from "fs";
import path from "path";

/** Spec-680 C1: «¿Cómo habla quien lo cuenta?» en «Tu idea». */
const VIEWS = path.join(process.cwd(), "src/views");
const state = JSON.parse(fs.readFileSync(path.join(process.cwd(), "tests/fixtures/asistente/estado.json"), "utf8"));

const HABLAS = [
  { id: "rioplatense", label: "Rioplatense", detail: "Como en Argentina y Uruguay." },
  { id: "mexicano", label: "De México", detail: "Como en México." },
];
const options = { effects: [], tellings: [], criteria: [], structures: [], forms: [], ingredients: [], hablas: HABLAS };

const render = (habla: string | undefined) =>
  ejs.renderFile(path.join(VIEWS, "asistente", "direccion.ejs"), {
    state: { ...state, direction: { ...state.direction, habla } },
    options,
    genres: [],
    estimateLabels: {},
    pasoActual: "direccion",
  });

const elegida = (html: string) =>
  [...html.matchAll(/<input type="radio" name="habla" value="([^"]+)"[^>]*?(checked)?>/g)]
    .filter((m) => m[2])
    .map((m) => m[1]);

describe("¿Cómo habla quien lo cuenta? (Spec-680 C1)", () => {
  it("una opción por habla, con su ayuda", async () => {
    const html = await render("mexicano");
    expect(html).toContain("¿Cómo habla quien lo cuenta?");
    expect(html).toContain("Como en México.");
    expect(elegida(html)).toEqual(["mexicano"]);
  });

  it("sin habla elegida (historias viejas), la de siempre", async () => {
    expect(elegida(await render(""))).toEqual(["rioplatense"]);
    expect(elegida(await render(undefined))).toEqual(["rioplatense"]);
  });

  it("el autoguardado la manda", () => {
    const js = fs.readFileSync(path.join(process.cwd(), "public/js/asistente.js"), "utf8");
    expect(js).toMatch(/habla: value\(form, "habla"\)/);
  });
});
