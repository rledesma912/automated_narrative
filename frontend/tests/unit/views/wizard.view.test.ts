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

/** Spec-440 T4.3: "quién cuenta la historia" filtrado en el render del servidor. */
describe("wizard paso 2 — narrador", () => {
  const step2 = STEPS[1];

  function render2(
    saved: Record<string, string>,
    characters: { value: string; label: string }[],
    fieldErrors: Record<string, string> = {},
  ) {
    return ejs.renderFile(viewPath, { steps: STEPS, step: step2, saved, isLast: false, characters, fieldErrors });
  }

  it("1 personaje: una sola opción con su nombre, preseleccionada", async () => {
    const sel = selectHtml(
      await render2({ protagonista_1_name: "Irene" }, [{ value: "protagonista_1", label: "Irene" }]),
      "storyteller_id",
    );
    expect(sel.match(/<option value="protagonista_/g)).toHaveLength(1);
    expect(sel).toContain('<option value="protagonista_1" selected>Irene</option>');
    expect(sel).not.toContain("Personaje");
  });

  it("varios personajes: conserva el narrador guardado", async () => {
    const sel = selectHtml(
      await render2({ storyteller_id: "protagonista_3" }, [
        { value: "protagonista_1", label: "Irene" },
        { value: "protagonista_3", label: "Ricardo" },
      ]),
      "storyteller_id",
    );
    expect(sel).toContain('<option value="protagonista_3" selected>Ricardo</option>');
    expect(sel).toContain('<option value="protagonista_1">Irene</option>');
  });

  it("sin personajes con nombre: deshabilitado con aviso", async () => {
    const sel = selectHtml(await render2({}, []), "storyteller_id");
    expect(sel).toMatch(/<select name="storyteller_id"[^>]* disabled/);
    expect(sel).toContain("Primero nombrá un personaje");
  });

  it("muestra el error del campo devuelto por el POST", async () => {
    const html = await render2({}, [], { storyteller_id: "Elegí uno de los personajes con nombre." });
    expect(html).toContain('data-field-error="storyteller_id">Elegí uno de los personajes con nombre.</p>');
  });
});

/** Spec-450 T4.1: grupo «La Amenaza» del paso 4. */
describe("wizard paso 4 — entidades", () => {
  const step4 = STEPS.find((s) => s.id === "step_world")!;
  const NATURES = [
    { id: "folklorica", label: "Ser del folklore" },
    { id: "desconocida", label: "Desconocida / ambigua" },
  ];

  function render4(saved: Record<string, string>, entityNatures: unknown) {
    return ejs.renderFile(viewPath, { steps: STEPS, step: step4, saved, isLast: false, entityNatures });
  }

  function cardHtml(html: string, n: number): string {
    return html.match(new RegExp(`<div id="entity-card-${n}"[^>]*>`))![0];
  }

  it("arranca sin cards visibles y con «Agregar entidad»", async () => {
    const html = await render4({}, NATURES);
    for (const n of [1, 2, 3]) expect(cardHtml(html, n)).toContain("hidden");
    expect(html).toContain('id="btn-add-entidad"');
    expect(html).toContain("ENTIDAD 1 — PRINCIPAL");
  });

  it("una entidad guardada: su card visible con la naturaleza seleccionada", async () => {
    const html = await render4({ entity_1_nature: "folklorica", entity_1_name: "La Mala Hora" }, NATURES);
    expect(cardHtml(html, 1)).not.toContain("hidden");
    expect(cardHtml(html, 2)).toContain("hidden");
    expect(selectHtml(html, "entity_1_nature")).toContain(
      '<option value="folklorica" selected>Ser del folklore</option>',
    );
  });

  it("sin género (o sin catálogo): naturaleza deshabilitada con aviso", async () => {
    const sel = selectHtml(await render4({}, null), "entity_1_nature");
    expect(sel).toMatch(/<select name="entity_1_nature"[^>]* disabled/);
    expect(sel).toContain("Elegí primero el tipo de horror (paso 1)");
  });

  it("los topes de largo del dominio van como maxlength", async () => {
    const html = await render4({}, NATURES);
    expect(html).toMatch(/name="entity_1_name"[^>]*maxlength="60"/);
    expect(html).toMatch(/name="entity_1_description"[^>]*maxlength="400"/);
  });
});

/** Estáticos versionados: cada deploy cambia la URL y el navegador no usa el JS viejo. */
describe("estáticos con versión", () => {
  it("wizard.js lleva ?v=<assetVersion>; sin versión, la URL sigue siendo válida", async () => {
    const withVersion = await ejs.renderFile(viewPath, {
      steps: STEPS, step: STEPS[0], saved: {}, isLast: false, assetVersion: "abc123",
    });
    expect(withVersion).toContain('src="/js/wizard.js?v=abc123"');
    const without = await ejs.renderFile(viewPath, { steps: STEPS, step: STEPS[0], saved: {}, isLast: false });
    expect(without).toContain('src="/js/wizard.js?v="');
  });
});
