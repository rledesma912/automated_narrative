/** Spec-440 T3.3: combos del catálogo renderizados en el servidor. */
import { describe, it, expect } from "vitest";
import ejs from "ejs";
import path from "path";
import { STEPS } from "../../../src/services/wizard.service";

const viewPath = path.join(process.cwd(), "src/views/wizard.ejs");
const CATALOG = [
  { id: "folk_horror", label: "Terror Rural", subgenres: [{ id: "rural", label: "Leyendas del campo" }] },
  { id: "suspenso", label: "Suspenso / Thriller", subgenres: [{ id: "acecho", label: "Acecho" }] },
];

function render(saved: Record<string, string>, genreCatalog: unknown) {
  return ejs.renderFile(viewPath, { steps: STEPS, step: STEPS[0], saved, isLast: false, genreCatalog });
}

function selectHtml(html: string, name: string): string {
  return html.match(new RegExp(`<select name="${name}"[\\s\\S]*?</select>`))![0];
}

describe("wizard paso 1 — género y subgénero", () => {
  it("género guardado: el subgénero lista solo los suyos, con el guardado seleccionado", async () => {
    const html = await render({ atmosfera: "folk_horror", atmosphere_subgenre: "rural" }, CATALOG);
    const sub = selectHtml(html, "atmosphere_subgenre");

    expect(selectHtml(html, "atmosfera")).toContain('<option value="folk_horror" selected>Terror Rural</option>');
    expect(sub).toContain('<option value="rural" selected>Leyendas del campo</option>');
    expect(sub).not.toContain("acecho");
    expect(sub).not.toContain(" disabled data-catalog-field");
    expect(html).toContain('<script type="application/json" id="genre-catalog">');
  });

  it("valor legado «id: Etiqueta» también queda seleccionado", async () => {
    const html = await render({ atmosfera: "folk_horror: Terror Rural (Leyendas de campo)" }, CATALOG);
    expect(selectHtml(html, "atmosfera")).toContain('value="folk_horror" selected');
  });

  it("sin género: subgénero deshabilitado con aviso", async () => {
    const sub = selectHtml(await render({}, CATALOG), "atmosphere_subgenre");
    expect(sub).toMatch(/<select name="atmosphere_subgenre"[^>]* disabled/);
    expect(sub).toContain("Elegí primero el tipo de horror");
  });

  it("Core caído: ambos combos deshabilitados, aviso y sin catálogo embebido", async () => {
    const html = await render({ atmosfera: "folk_horror" }, null);

    expect(selectHtml(html, "atmosfera")).toMatch(/<select name="atmosfera"[^>]* disabled/);
    expect(selectHtml(html, "atmosphere_subgenre")).toMatch(/ disabled/);
    expect(html).toContain("data-catalog-error");
    expect(html).not.toContain('id="genre-catalog"');
  });
});
