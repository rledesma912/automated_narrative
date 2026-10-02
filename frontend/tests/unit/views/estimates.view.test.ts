import { describe, it, expect } from "vitest";
import ejs from "ejs";
import path from "path";
import { rutas } from "../../../src/utils/rutas";

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

// Spec-630: la galería ya no lanza jobs (B14) y la ficha se fue (B12): no muestran estimación.
describe("galería", () => {
  it.each(["draft", "failed", "completed"])("no muestra estimación (%s)", async (status) => {
    const html = await ejs.renderFile(view("gallery.ejs"), {
      rutas,
      stories: [story(status)],
      estimateLabels: LABELS,
    });
    expect(html).not.toContain("data-estimate");
  });
});

describe("sala: confirmación", () => {
  const room = (regenerateMode: boolean, estimateLabels: unknown) =>
    ejs.renderFile(view("streaming-room.ejs"), {
      rutas,
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
      "Tarda ≈ 4 min. Podés cerrar la pestaña: la IA sigue escribiendo.",
    );
  });

  it("sin estimación, igual avisa que se puede cerrar la pestaña", async () => {
    const text = (await room(false, null)).replace(/\s+/g, " ");
    expect(text).toContain("Podés cerrar la pestaña: la IA sigue escribiendo.");
    expect(text).not.toContain("Tarda");
  });
});

// Spec-630 B14: un borrador con ?escribir=1 ve «¿Empezamos a escribir?»; sin eso, «Escribir el relato».
describe("sala: un borrador", () => {
  const base = { rutas, storyId: "s-1", story: story("draft"), beats: [], storyStatus: "draft", regenerateMode: false, activeJobId: null };

  it("con startMode muestra el panel para empezar", async () => {
    const html = (await ejs.renderFile(view("streaming-room.ejs"), { ...base, startMode: true })).replace(/\s+/g, " ");
    expect(html).toContain("¿Empezamos a escribir?");
    expect(html).toContain('onclick="initiateGeneration()"');
  });

  it("en modo lectura ofrece «Escribir el relato» con ?escribir=1", async () => {
    const html = await ejs.renderFile(view("streaming-room.ejs"), { ...base, startMode: false });
    expect(html).toMatch(/href="\/generar\/stream\/s-1\?escribir=1"[^>]*>\s*<i[^>]*><\/i> Escribir el relato/);
    expect(html).toContain('href="/asistente/s-1/escaleta"');
  });
});

describe("relatos: regenerar un acto", () => {
  const panel = (estimateLabels: unknown) =>
    ejs.renderFile(view("partials/relato_panel.ejs"), {
      story: { id: "s-1" },
      relato: { id: "r-1", content: "## Acto 1\n\nUno." },
      isActive: true,
      regenerating: null,
      panelError: null,
      estimateLabels,
    });

  it("la confirmación dice cuánto tarda", async () => {
    expect(await panel(LABELS)).toContain(
      'hx-confirm="Tarda ≈ 1 min. Se reemplaza el texto actual del acto 1."',
    );
  });

  it("sin estimación, la confirmación de siempre", async () => {
    expect(await panel(null)).toContain(
      'hx-confirm="Se reemplaza el texto actual del acto 1."',
    );
  });
});
