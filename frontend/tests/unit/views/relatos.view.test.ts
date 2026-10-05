import { describe, it, expect } from "vitest";
import ejs from "ejs";
import path from "path";

const viewPath = path.join(process.cwd(), "src/views/relatos.ejs");
const panelPath = path.join(process.cwd(), "src/views/partials/relato_panel.ejs");

const CONTENT = "## Acto 1\n\nPrimera prosa.\n\n## Acto 2\n\nSegunda prosa.";

function renderPanel(regenerating: { acto: number; jobId: string } | null = null) {
  return ejs.renderFile(panelPath, {
    story: { id: "s-1" },
    relato: { id: "r-1", content: CONTENT },
    isActive: true,
    regenerating,
    panelError: null,
    conAcciones: true, // como lo sirve el Express (Spec-630 B15)
  });
}

/** El tag de apertura del enlace de descarga (sin DOM: vitest corre en node). */
function downloadTag(html: string): string {
  const match = html.match(/<a\b[^>]*data-descargar-relato="r-1"[^>]*>/);
  expect(match).not.toBeNull();
  return match![0];
}

/** Texto de cada elemento con data-copy-part, en orden. */
function copyParts(html: string): string[] {
  const re = /<(\w+)\b[^>]*\bdata-copy-part\b[^>]*>([\s\S]*?)<\/\1>/g;
  return Array.from(html.matchAll(re), (m) => m[2].trim());
}

describe("relatos view", () => {
  it("renders a top switcher for multiple generated narratives", async () => {
    const html = await ejs.renderFile(viewPath, {
      story: { id: "s-1", title: "La casa", status: "completed" },
      relatos: [
        {
          id: "r-1",
          title: "Primera versión",
          content: "Texto 1",
          created_at: "2026-05-05T10:00:00.000Z",
        },
        {
          id: "r-2",
          title: "Segunda versión",
          content: "Texto 2",
          created_at: "2026-05-05T11:00:00.000Z",
        },
      ],
    });

    expect(html).toContain("data-relato-tab=\"r-1\"");
    expect(html).toContain("data-relato-tab=\"r-2\"");
    expect(html).toContain("data-relato-panel=\"r-1\"");
    expect(html).toContain("data-relato-panel=\"r-2\"");
    expect(html).toContain("Copiar Relato");
  });

  // Spec-630 B13: la pestaña no repite el título de la historia; dice solo la fecha.
  it("cada pestaña dice «Versión del dd/mm/yyyy hh:mm» (hora de Argentina)", async () => {
    const html = await ejs.renderFile(viewPath, {
      story: { id: "s-1", title: "La casa", status: "completed" },
      relatos: [
        { id: "r-1", title: "La casa", content: "## Acto 1\n\nUno.", created_at: "2026-10-02T17:30:00.000Z" },
      ],
    });
    expect(html).toContain("Versión del 02/10/2026 14:30");
    const tab = html.match(/<button[^>]*data-relato-tab="r-1"[^>]*>([\s\S]*?)<\/button>/)![1];
    expect(tab).not.toContain("La casa");
    expect(html).not.toMatch(/<h3[^>]*>\s*La casa\s*<\/h3>/);
  });

  // Spec-630 B16: «El relato» tiene la barra con los pasos, para volver a los anteriores.
  it("tiene la barra con los cuatro pasos y «El relato» como actual", async () => {
    const html = await ejs.renderFile(viewPath, {
      story: { id: "s-1", title: "La casa", status: "completed" },
      relatos: [],
    });
    expect(html).toContain('class="asistente-barra"');
    expect(html).toContain('href="/asistente/s-1/direccion"');
    expect(html).toContain('href="/asistente/s-1/taller"');
    expect(html).toContain('href="/asistente/s-1/escaleta"');
    expect(html).toMatch(/aria-current="step"[^>]*>[\s\S]*?El relato/);
    expect(html).not.toContain("Volver a Galería");
  });

  it("renders an explicit empty state when there are no narratives", async () => {
    const html = await ejs.renderFile(viewPath, {
      story: { id: "s-1", title: "La casa", status: "completed" },
      relatos: [],
    });

    expect(html).toContain("Todavía no hay relatos de esta historia.");
    expect(html).not.toContain("data-relato-tab=");
  });

  // Spec-490 T2.1
  it("renders a download link to the .md export next to Copiar Relato", async () => {
    const html = await renderPanel();
    const tag = downloadTag(html);

    expect(tag).toContain('href="/api/v1/generated-narratives/r-1/export.md"');
    expect(tag).toMatch(/\sdownload[\s>]/);
    expect(tag).not.toContain("aria-disabled");
    // Sin hx-boost: htmx convertiría la descarga en un swap AJAX.
    expect(tag).toContain('hx-boost="false"');
    expect(html).toContain("Descargar .md");
    expect(html.indexOf("Descargar .md")).toBeLessThan(html.indexOf("Copiar Relato"));
  });

  it("disables the download link while an act is regenerating", async () => {
    const tag = downloadTag(await renderPanel({ acto: 2, jobId: "j-1" }));

    expect(tag).not.toContain("href=");
    expect(tag).not.toMatch(/\sdownload[\s>]/);
    expect(tag).toContain('aria-disabled="true"');
  });

  // Spec-490 T2.2
  it("marks act labels and prose as copy parts, in order, without buttons", async () => {
    const html = await renderPanel();
    const parts = copyParts(html);

    expect(parts).toEqual(["Acto 1", "Primera prosa.", "Acto 2", "Segunda prosa."]);
    expect(parts.join(" ")).not.toMatch(/<button|<a\b|Regenerar/);
    expect(html.match(/data-regenerar-acto=/g)).toHaveLength(2);
  });
});

describe("relato_panel — control de repetición (Spec-530 §8.3)", () => {
  it("muestra lo que repite cada acto y no lo copia", async () => {
    const html = await ejs.renderFile(panelPath, {
      story: { id: "s-1" },
      relato: {
        id: "r-1",
        content: CONTENT,
        repetition: {
          acts: [
            { number: 1, repeated: [], cliches: [] },
            {
              number: 2,
              repeated: ["«el olor dulce» (del acto 1)"],
              cliches: ["me heló la sangre"],
              invented_names: ["Laura"],
            },
          ],
        },
      },
      isActive: true,
      regenerating: null,
      panelError: null,
    });

    expect(html.match(/data-repeticion/g)).toHaveLength(1);
    expect(html).toContain("Repite 1 frase de actos anteriores · 1 cliché · 1 nombre inventado");
    expect(html).toContain("Nombres que no están en la historia: Laura");
    expect(html).toContain("Cliché: «me heló la sangre»");
    expect(copyParts(html).join(" ")).not.toContain("Repite");
  });

  // Spec-590 F: oraciones cortadas (solo si pasan a ser el estilo del acto) y diálogo.
  it("avisa oraciones cortadas y diálogo", async () => {
    const html = await ejs.renderFile(panelPath, {
      story: { id: "s-1" },
      relato: {
        id: "r-1",
        content: CONTENT,
        repetition: {
          acts: [
            { number: 1, repeated: [], cliches: [], cut_sentences: ["Solo."], cut_count: 1, cut_pct: 5, too_cut: false, dialogue: 0 },
            { number: 2, repeated: [], cliches: [], cut_sentences: ["Un sonido.", "Más cerca."], cut_count: 12, cut_pct: 40, too_cut: true, dialogue: 2 },
          ],
        },
      },
      isActive: true,
      regenerating: null,
      panelError: null,
    });

    expect(html.match(/data-repeticion/g)).toHaveLength(1); // el acto 1 no avisa por un fragmento
    expect(html).toContain("12 oraciones cortadas · tiene diálogo");
    expect(html).toContain("Oraciones cortadas: 12 de este acto (40 %), por ejemplo «Un sonido.», «Más cerca.»");
    expect(html).toContain("Diálogo: 2 frases con raya o entre comillas");
    expect(copyParts(html).join(" ")).not.toContain("oraciones cortadas");
  });

  // Spec-640: comparaciones de escritor, desde la segunda del acto.
  it("avisa las comparaciones cuando pasan de una por acto", async () => {
    const base = { repeated: [], cliches: [], cut_sentences: [], cut_count: 0, cut_pct: 0, too_cut: false, dialogue: 0 };
    const html = await ejs.renderFile(panelPath, {
      story: { id: "s-1" },
      relato: {
        id: "r-1",
        content: CONTENT,
        repetition: {
          acts: [
            { number: 1, ...base, comparisons: ["como si le pesara"], comparison_count: 1, too_literary: false },
            { number: 2, ...base, comparisons: ["como si le pesara", "como una cortina"], comparison_count: 3, too_literary: true },
          ],
        },
      },
      isActive: true,
      regenerating: null,
      panelError: null,
    });
    expect(html.match(/data-repeticion/g)).toHaveLength(1);
    expect(html).toContain("3 comparaciones");
    expect(html).toContain("Comparaciones: 3 en este acto, por ejemplo «como si le pesara…», «como una cortina…»");
    expect(copyParts(html).join(" ")).not.toContain("Comparaciones");
  });

  it("sin control de repetición (Core caído) el panel se ve como antes", async () => {
    const html = await renderPanel();
    expect(html).not.toContain("data-repeticion");
  });
});

// Spec-560 A2: el panel avisa qué actos se escribieron con la versión anterior.
describe("actos desactualizados", () => {
  it("avisa en el panel activo solo en los actos marcados", async () => {
    const html = await ejs.renderFile(path.join(process.cwd(), "src/views/partials/relato_panel.ejs"), {
      story: { id: "s-1", stale_acts: [3] },
      relato: { id: "r-1", content: "## Acto 2\n\nDos.\n\n## Acto 3\n\nTres." },
      isActive: true,
      regenerating: null,
      panelError: null,
    });
    expect((html.match(/data-acto-desactualizado/g) || []).length).toBe(1);
    expect(html.indexOf("data-acto-desactualizado")).toBeGreaterThan(html.indexOf("Acto 3"));
  });

  // ── Spec-630 B15: las acciones, agrupadas arriba ─────────────────────────────

  const DOS = {
    story: { id: "s-1", title: "La casa", status: "completed" },
    relatos: [
      { id: "r-1", content: "## Acto 1\n\nUno.", created_at: "2026-10-02T17:30:00.000Z" },
      { id: "r-2", content: "## Acto 1\n\nDos.", created_at: "2026-10-01T17:30:00.000Z", hasVideoScript: true },
    ],
  };

  it("el panel de acciones va antes de las pestañas, con un grupo por versión", async () => {
    const html = await ejs.renderFile(viewPath, DOS);
    const acciones = html.indexOf("data-relato-acciones");
    expect(acciones).toBeGreaterThan(-1);
    expect(acciones).toBeLessThan(html.indexOf("data-relato-tab="));
    const grupo = (id: string) => html.match(new RegExp(`<div id="relato-acciones-${id}"[^>]*class="([^"]*)"`))![1];
    expect(grupo("r-1")).toMatch(/\bflex\b/);
    expect(grupo("r-2")).toMatch(/\bhidden\b/);
    // Cada grupo con lo suyo: corregir, guion / para el video, descargar y copiar.
    for (const id of ["r-1", "r-2"]) {
      expect(html).toContain(`data-corregir-relato="${id}"`);
      expect(html).toContain(`data-descargar-relato="${id}"`);
      expect(html).toContain(`copyRelatoContent('${id}', this)`);
    }
    expect(html).toContain('data-armar-guion="r-1"');
    expect(html).toContain('data-para-el-video="r-2"');
  });

  // Spec-630 B19: se llama «Regenerar historia», como en el resto del sitio.
  it("«Regenerar historia» va a la sala, que confirma", async () => {
    const html = await ejs.renderFile(viewPath, DOS);
    expect(html).toMatch(
      /<a href="\/generar\/stream\/s-1\?escribir=1"[^>]*data-generation-trigger[^>]*>\s*<i[^>]*><\/i> Regenerar historia/,
    );
    expect(html).not.toContain("Escribir de nuevo");
  });

  it("el panel de la versión trae la prosa y «Regenerar» por acto, sin las acciones", async () => {
    const html = await ejs.renderFile(panelPath, {
      story: { id: "s-1" },
      relato: { id: "r-1", content: CONTENT },
      isActive: true,
      regenerating: null,
      panelError: null,
    });
    expect(html).not.toContain("data-descargar-relato");
    expect(html).not.toContain("data-corregir-relato");
    expect(html).not.toContain("copyRelatoContent");
    expect(html).toContain('data-regenerar-acto="1"');
  });

  it("al regenerar un acto, el grupo de esa versión viaja fuera de banda y deshabilitado", async () => {
    const html = await renderPanel({ acto: 2, jobId: "j-1" });
    expect(html).toMatch(/<div id="relato-acciones-r-1"[^>]*hx-swap-oob="outerHTML"/);
    expect(html).toMatch(/data-corregir-relato="r-1"[\s\S]*?opacity-40/);
  });
});
