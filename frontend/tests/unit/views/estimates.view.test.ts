import { describe, it, expect } from "vitest";
import ejs from "ejs";
import path from "path";

/** Spec-510 T3.2: «≈ N min» antes de lanzar un job. */

const view = (name: string) => path.join(process.cwd(), "src/views", name);
const LABELS = { full_generation: "≈ 4 min", regenerate_voz: "≈ 1 min" };

function story(status: string) {
  return {
    id: "s-1",
    title: "La casa",
    status,
    created_at: "2026-05-05T10:00:00.000Z",
    protagonista: "Ana",
    relator: "Primera persona",
    sinopsis: "Algo pasa.",
    genero: "paranormal",
    subgenero: "fantasmas",
    characters: [],
    rules: [],
    scenarios: [],
    entities: [],
  };
}

describe("galería", () => {
  it.each(["draft", "failed", "completed"])("muestra la estimación junto al botón (%s)", async (status) => {
    const html = await ejs.renderFile(view("gallery.ejs"), {
      stories: [story(status)],
      estimateLabels: LABELS,
    });
    expect(html).toContain('data-estimate="full_generation"');
    expect(html).toMatch(/<\/button>\s*<span[^>]*data-estimate="full_generation"[^>]*>≈ 4 min<\/span>/);
  });

  it("sin estimación no muestra nada", async () => {
    const html = await ejs.renderFile(view("gallery.ejs"), { stories: [story("draft")] });
    expect(html).not.toContain("data-estimate");
  });
});

describe("ficha", () => {
  it.each(["draft", "completed"])("muestra la estimación junto a Generar/Regenerar (%s)", async (status) => {
    const html = await ejs.renderFile(view("historia.ejs"), {
      story: story(status),
      pageError: null,
      estimateLabels: LABELS,
    });
    expect(html.match(/data-estimate="full_generation"/g)).toHaveLength(1);
  });

  it("sin estimación no muestra nada", async () => {
    const html = await ejs.renderFile(view("historia.ejs"), { story: story("draft"), pageError: null });
    expect(html).not.toContain("data-estimate");
  });
});

describe("sala: confirmación", () => {
  const room = (regenerateMode: boolean, estimateLabels: unknown) =>
    ejs.renderFile(view("streaming-room.ejs"), {
      storyId: "s-1",
      // Sin regenerar, el panel de inicio solo aparece con la historia en `processing`.
      story: story(regenerateMode ? "completed" : "processing"),
      beats: [],
      storyStatus: regenerateMode ? "completed" : "processing",
      regenerateMode,
      activeJobId: null,
      estimateLabels,
    });

  it.each([true, false])("dice cuánto tarda y que se puede cerrar la pestaña (regenerar: %s)", async (mode) => {
    const html = await room(mode, LABELS);
    expect(html.replace(/\s+/g, " ")).toContain(
      "Tarda ≈ 4 min. Podés cerrar la pestaña: sigue generándose.",
    );
  });

  it("sin estimación, igual avisa que se puede cerrar la pestaña", async () => {
    const text = (await room(false, null)).replace(/\s+/g, " ");
    expect(text).toContain("Podés cerrar la pestaña: sigue generándose.");
    expect(text).not.toContain("Tarda");
  });
});

describe("relatos: regenerar un acto", () => {
  const panel = (estimateLabels: unknown) =>
    ejs.renderFile(view("partials/relato_panel.ejs"), {
      story: { id: "s-1" },
      relato: { id: "r-1", content: "## Acto 1\n\nUno." },
      displayTitle: "Primera versión",
      isActive: true,
      regenerating: null,
      panelError: null,
      estimateLabels,
    });

  it("la confirmación dice cuánto tarda", async () => {
    expect(await panel(LABELS)).toContain(
      'hx-confirm="¿Regenerar este acto? Tarda ≈ 1 min. Se reemplazará el texto actual."',
    );
  });

  it("sin estimación, la confirmación de siempre", async () => {
    expect(await panel(null)).toContain(
      'hx-confirm="¿Regenerar este acto? Se reemplazará el texto actual."',
    );
  });
});
