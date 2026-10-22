import { describe, it, expect } from "vitest";
import ejs from "ejs";
import fs from "fs";
import path from "path";

/** Spec-690: «¿Cómo termina?» sale de «Tu idea»; el final sacado de la idea se ve en «Preguntas». */
const VIEWS = path.join(process.cwd(), "src/views");
const state = JSON.parse(fs.readFileSync(path.join(process.cwd(), "tests/fixtures/asistente/estado.json"), "utf8"));

const conFinal = (final: Record<string, unknown>) => ({
  ...state,
  workshop: {
    ...state.workshop,
    items: state.workshop.items.map((i: { criterion: string }) => (i.criterion === "final" ? { ...i, ...final } : i)),
  },
});

const taller = (s: unknown) =>
  ejs.renderFile(path.join(VIEWS, "asistente", "_taller_contenido.ejs"), { state: s, estimateLabels: {} });

const final = (html: string) => html.match(/<li[^>]*data-pregunta="final"[\s\S]*?<\/li>/)![0];

describe("Tu idea sin «¿Cómo termina?» (Spec-690)", () => {
  it("no tiene el campo y la ayuda de «¿De qué trata?» invita a contar el final", async () => {
    const options = { effects: [], tellings: [], criteria: [], structures: [], forms: [], ingredients: [], hablas: [] };
    const html = await ejs.renderFile(path.join(VIEWS, "asistente", "direccion.ejs"), {
      state,
      options,
      genres: [],
      estimateLabels: {},
      pasoActual: "direccion",
    });
    expect(html).not.toContain("¿Cómo termina?");
    expect(html).not.toContain('name="ending"');
    expect(html).toContain("de punta a punta: qué pasa y cómo termina, si ya lo sabés");
  });

  it("el autoguardado ya no manda el final", () => {
    const js = fs.readFileSync(path.join(process.cwd(), "public/js/asistente.js"), "utf8");
    expect(js).not.toMatch(/ending: value\(form/);
  });
});

describe("Preguntas: el final de la idea (Spec-690)", () => {
  it("se marca «De tu idea» con su pista", async () => {
    const html = await taller(
      conFinal({ status: "intencional", answer: "Al final la deja bajar.", de_la_idea: true }),
    );
    const li = final(html);
    expect(li).toContain("De tu idea");
    expect(li).toContain("Al final la deja bajar.");
    expect(li).toContain("Lo sacamos de tu idea. Si no es así, tocá «Cambiar»");
    expect(li).toContain("data-cambiar");
  });

  it("un final que no salió de la idea se ve como siempre", async () => {
    const li = final(await taller(conFinal({ status: "intencional", answer: "Se va.", de_la_idea: false })));
    expect(li).toContain("A propósito");
    expect(li).not.toContain("De tu idea");
  });
});
