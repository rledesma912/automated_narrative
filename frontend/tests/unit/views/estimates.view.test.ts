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

// Spec-660 B1: la sala ya no pregunta. Sin job muestra lo que hay, con un botón que
// pregunta ahí mismo (con el tiempo estimado); con job, el avance.
describe("sala", () => {
  const sala = (extra: Record<string, unknown>) =>
    ejs.renderFile(view("streaming-room.ejs"), {
      rutas,
      storyId: "s-1",
      story: story("completed"),
      beats: [],
      storyStatus: "completed",
      activeJobId: null,
      estimateLabels: LABELS,
      ...extra,
    });
  const boton = (html: string) => html.match(/<button[^>]*data-escribir-relato[^>]*>[\s\S]*?<\/button>/)![0];

  it.each([
    ["completed", "Regenerar historia", true],
    ["failed", "Regenerar historia", false],
    ["draft", "Escribir el relato", false],
  ])("sin job (%s) no pregunta: ofrece «%s», que lleva el tiempo estimado", async (status, texto, nueva) => {
    const html = await sala({ storyStatus: status, story: story(status) });
    expect(html).not.toContain("start-panel");
    expect(html).not.toContain("¿Regeneramos la historia?");
    expect(html).not.toContain("¿Empezamos a escribir?");
    const b = boton(html);
    expect(b).toContain(texto);
    expect(b).toContain('data-estimado="≈ 4 min"');
    expect(b).toContain("data-generation-trigger");
    expect(b.includes("data-version-nueva")).toBe(nueva);
    expect(html).not.toContain('action="/historia/s-1/generar"'); // D2
  });

  it("sin estimación, el botón igual pregunta (sin tiempo)", async () => {
    expect(boton(await sala({ estimateLabels: null }))).toContain('data-estimado=""');
  });

  it("con la IA escribiendo muestra el avance y no un botón para escribir", async () => {
    const html = await sala({ activeJobId: "j-1", storyStatus: "processing", story: story("processing") });
    expect(html).toContain("Escribiendo tu relato");
    expect(html).toContain('id="beat-dots"');
    expect(html).not.toContain("data-escribir-relato");
    expect(html).not.toContain("initiateGeneration");
  });

  it("«Reintentar» lleva la historia y el tiempo estimado para preguntar (D3)", async () => {
    const html = await sala({ activeJobId: "j-1", storyStatus: "processing", story: story("processing") });
    expect(html).toMatch(/onclick="retryStream\(this\)" data-story-id="s-1"\s+data-estimado="≈ 4 min"/);
  });

  it.each([
    ["sin job", {}],
    ["con la IA escribiendo", { activeJobId: "j-1", storyStatus: "processing", story: story("processing") }],
  ])("se puede volver a Mis historias y a «Los actos» (%s)", async (_caso, extra) => {
    const html = await sala(extra);
    expect(html).toMatch(/href="\/galeria"/);
    expect(html).toMatch(/href="\/asistente\/s-1\/escaleta"/);
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
