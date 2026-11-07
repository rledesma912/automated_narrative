import { describe, it, expect } from "vitest";
import ejs from "ejs";
import path from "path";

/** Spec-740 C2/C3: «Lo escribió …» en cada versión del relato. */
const panel = path.join(process.cwd(), "src/views/partials/relato_panel.ejs");
const CONTENT = "## Acto 1\n\nUno.\n\n## Acto 2\n\nDos.\n\n## Acto 3\n\nTres.";
const render = (ia: unknown) =>
  ejs.renderFile(panel, {
    story: { id: "s-1" },
    relato: { id: "r-1", content: CONTENT, ia },
    isActive: true,
    regenerating: null,
    panelError: null,
    conAcciones: true,
  });
const texto = (html: string) =>
  (html.match(/<div[^>]*data-ia-relato[^>]*>[\s\S]*?<\/p>/) || [""])[0].replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();

const RESTO = [{ tarea: "Armar los actos", nombre: "Qwen 3.8" }];

describe("qué IA escribió el relato (Spec-740 C2)", () => {
  it("un solo modelo: «Lo escribió …», sin marca por acto", async () => {
    const html = await render({ modelos: [{ nombre: "Gemini 3.1 Flash Lite", actos: [1, 2, 3] }], por_acto: { 1: "Gemini 3.1 Flash Lite", 2: "Gemini 3.1 Flash Lite", 3: "Gemini 3.1 Flash Lite" }, resto: RESTO });
    expect(texto(html)).toBe("Lo escribió Gemini 3.1 Flash Lite.");
    expect(html).not.toContain("data-ia-acto");
  });

  it("varios: «Lo escribieron A (actos 1 y 2) y B (acto 3)», y cada acto dice el suyo", async () => {
    const html = await render({
      modelos: [{ nombre: "Gemini 3.1 Flash Lite", actos: [1, 2] }, { nombre: "Qwen 3.8", actos: [3] }],
      por_acto: { 1: "Gemini 3.1 Flash Lite", 2: "Gemini 3.1 Flash Lite", 3: "Qwen 3.8" },
      resto: RESTO,
    });
    expect(texto(html)).toBe("Lo escribieron Gemini 3.1 Flash Lite (actos 1 y 2) y Qwen 3.8 (acto 3).");
    expect(html).toMatch(/data-ia-acto="3">Qwen 3.8</);
  });

  it("actos seguidos van con «a», salteados con comas", async () => {
    const html = await render({
      modelos: [{ nombre: "A", actos: [1, 2, 3] }, { nombre: "B", actos: [4] }, { nombre: "C", actos: [5] }],
      por_acto: {},
      resto: [],
    });
    expect(texto(html)).toBe("Lo escribieron A (actos 1 a 3), B (acto 4) y C (acto 5).");
    const salteados = await render({ modelos: [{ nombre: "A", actos: [1, 3, 5] }, { nombre: "B", actos: [2, 4] }], por_acto: {}, resto: [] });
    expect(texto(salteados)).toBe("Lo escribieron A (actos 1, 3 y 5) y B (actos 2 y 4).");
  });

  it("el resto del trabajo va plegado", async () => {
    const html = await render({ modelos: [{ nombre: "A", actos: [1] }], por_acto: {}, resto: RESTO });
    expect(html).toMatch(/<details[^>]*data-ia-detalle[\s\S]*Ver qué IA hizo cada cosa[\s\S]*Armar los actos: Qwen 3.8/);
  });

  it("sin dato (relatos viejos) o si el Core no respondió, no dice nada", async () => {
    for (const ia of [undefined, null, { modelos: [], por_acto: {}, resto: [] }]) {
      expect(await render(ia)).not.toContain("data-ia-relato");
    }
  });

  it("no se copia con el relato", async () => {
    const html = await render({ modelos: [{ nombre: "A", actos: [1, 2] }, { nombre: "B", actos: [3] }], por_acto: { 1: "A", 2: "A", 3: "B" }, resto: [] });
    expect(html).not.toMatch(/data-copy-part[^>]*>[^<]*(Lo escribi|Qwen|A<)/);
    expect(html).not.toMatch(/<[^>]*data-ia-(relato|acto)[^>]*data-copy-part/);
  });
});
