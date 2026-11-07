import { describe, it, expect } from "vitest";
import ejs from "ejs";
import fs from "fs";
import path from "path";

/** Spec-740 C6: con el largo deshabilitado (sin crédito), las historias largas no usan la IA. */
const VIEWS = path.join(process.cwd(), "src/views");
const estado = JSON.parse(
  fs.readFileSync(path.join(process.cwd(), "tests/fixtures/asistente/estado.json"), "utf8"),
);
const NOTA = "Por ahora no se pueden escribir historias medias.";
const apagada = { ia_disponible: false, ia_nota: NOTA };
const LARGOS = [
  { id: "medio", label: "Media · 5 actos · unos 15 minutos", acts: 5, disponible: false, nota: NOTA },
  { id: "corto", label: "Corto · 3 actos · unos 7 minutos", acts: 3, disponible: true, nota: null },
];
const options = { effects: [], tellings: [], criteria: [], structures: LARGOS, forms: [], ingredients: [], hablas: [] };

const asistente = (paso: string, state: object | null) =>
  ejs.renderFile(path.join(VIEWS, "asistente", `${paso}.ejs`), {
    state,
    options,
    genres: [],
    estimateLabels: {},
    pasoActual: paso,
  });

/** Los botones que lanzan la IA, con su tag de apertura completo. */
const botonesDeIa = (html: string) =>
  [...html.matchAll(/<button\b(?:%>|[^>])*?\b(?:data-analizar=|data-escribir-relato|data-regenerar|data-armar-guion|data-rearmar)(?:[^>])*>/g)].map(
    (m) => m[0],
  );

describe("el largo deshabilitado (Spec-740 C6)", () => {
  it("«¿Qué tan largo?» muestra el largo apagado con la nota, y una historia nueva arranca en corto", async () => {
    const html = await asistente("direccion", null);
    expect(html).toMatch(/<input type="radio" name="structure" value="medio"[^>]*disabled/);
    expect(html).toMatch(/<input type="radio" name="structure" value="corto"[^>]*checked/);
    expect(html).not.toMatch(/<input type="radio" name="structure" value="corto"[^>]*disabled/);
    expect(html).toContain(`data-largo-nota="medio"`);
    expect(html).toContain(NOTA);
  });

  for (const paso of ["direccion", "taller", "escaleta"]) {
    it(`en «${paso}», una historia larga muestra la nota y sus botones de IA no se pueden tocar`, async () => {
      const html = await asistente(paso, { ...estado, structure: "medio", ...apagada });
      expect(html).toContain("data-ia-apagada-nota");
      expect(html).toContain(`href="/asistente/${estado.story_id}/direccion#largo">Cambiar el largo`);
      const botones = botonesDeIa(html);
      expect(botones.length).toBeGreaterThan(0);
      for (const b of botones) expect(b).toMatch(/data-ia-apagada disabled/);
    });

    it(`en «${paso}», con IA disponible no cambia nada`, async () => {
      const html = await asistente(paso, { ...estado, ia_disponible: true, ia_nota: null });
      expect(html).not.toContain("data-ia-apagada");
    });
  }

  it("en «El relato», la nota y los botones de regenerar y guion apagados", async () => {
    const story = { id: "s-1", title: "La casa", status: "completed", structure: "medio", ...apagada };
    const html = await ejs.renderFile(path.join(VIEWS, "relatos.ejs"), {
      story,
      relatos: [{ id: "r-1", title: "V", content: "## Acto 1\n\nProsa.", created_at: "2026-11-06T10:00:00.000Z" }],
    });
    expect(html).toContain("data-ia-apagada-nota");
    const botones = botonesDeIa(html);
    expect(botones.length).toBeGreaterThan(0);
    for (const b of botones) expect(b).toMatch(/data-ia-apagada disabled/);
  });

  it("el guardia de clic se carga en todas las páginas", () => {
    const layout = fs.readFileSync(path.join(VIEWS, "partials", "layout.ejs"), "utf8");
    expect(layout).toContain("/js/ia-apagada.js");
    const js = fs.readFileSync(path.join(process.cwd(), "public/js/ia-apagada.js"), "utf8");
    expect(js).toMatch(/closest\("\[data-ia-apagada\]"\)/);
    expect(js).toMatch(/stopImmediatePropagation/);
  });
});
