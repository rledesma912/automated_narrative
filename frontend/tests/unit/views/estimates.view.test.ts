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

  it("en modo lectura ofrece «Escribir el relato», que pregunta ahí mismo (Spec-660)", async () => {
    const html = await ejs.renderFile(view("streaming-room.ejs"), { ...base, startMode: false });
    expect(html).toMatch(/<button[^>]*data-escribir-relato[^>]*data-estimado="[^"]*"[^>]*>\s*<i[^>]*><\/i> Escribir el relato/);
    expect(html).not.toContain("data-version-nueva");
    expect(html).toContain('href="/asistente/s-1/escaleta"');
  });
});

// Spec-630 B18–B20: la sala al escribir (confirmar o con la IA trabajando).
describe("sala: escribir", () => {
  const sala = (extra: Record<string, unknown>) =>
    ejs.renderFile(view("streaming-room.ejs"), {
      rutas,
      storyId: "s-1",
      story: story("completed"),
      beats: [],
      storyStatus: "completed",
      regenerateMode: false,
      startMode: false,
      activeJobId: null,
      ...extra,
    });

  it.each([
    ["confirmar la regeneración", { regenerateMode: true }],
    ["empezar un borrador", { startMode: true, storyStatus: "draft", story: story("draft") }],
    ["con la IA escribiendo", { activeJobId: "j-1", storyStatus: "processing", story: story("processing") }],
  ])("se puede volver a Mis historias y a «Los actos» (%s)", async (_caso, extra) => {
    const html = await sala(extra);
    const nav = html.match(/<nav[^>]*data-sala-volver[^>]*>([\s\S]*?)<\/nav>/)![1];
    expect(nav).toMatch(/href="\/galeria" hx-boost="false"/);
    expect(nav).toMatch(/href="\/asistente\/s-1\/escaleta" hx-boost="false"/);
  });

  it("confirma «¿Regeneramos la historia?» con «Regenerar historia» (B19)", async () => {
    const html = (await sala({ regenerateMode: true })).replace(/\s+/g, " ");
    expect(html).toContain("¿Regeneramos la historia?");
    expect(html).toMatch(/onclick="initiateRegeneration\(\)"[^>]*>[^<]*<i[^>]*><\/i> Regenerar historia/);
    expect(html).not.toContain("Escribirla de nuevo");
  });

  it("avisa que sale una versión nueva y que las otras quedan (B20)", async () => {
    const html = (await sala({ regenerateMode: true })).replace(/\s+/g, " ");
    expect(html).toMatch(/nota-forge--info[^>]*data-version-nueva/);
    expect(html).toContain("Se escribe una versión nueva con lo que tenés en «Los actos». Las versiones que ya tenés quedan en «El relato».");
    expect(html).not.toContain("se reemplaza");
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
