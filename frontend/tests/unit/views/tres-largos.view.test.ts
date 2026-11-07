import { describe, it, expect } from "vitest";
import ejs from "ejs";
import path from "path";
import { rutas } from "../../../src/utils/rutas";

/** Spec-750 S5: «¿Qué tan largo?» con tres opciones y el chip de la larga. */
const VIEWS = path.join(process.cwd(), "src/views");
const largo = (id: string, label: string, acts: number, extra: object = {}) => ({
  id,
  label,
  acts,
  disponible: true,
  nota: null,
  por_defecto: id === "medio",
  ...extra,
});
const LARGOS = [
  largo("corto", "Corto · 3 actos · unos 7 minutos", 3),
  largo("medio", "Media · 5 actos · unos 15 minutos", 5),
  largo("largo", "Larga · 5 actos · unos 35 minutos", 5),
];
const direccion = (structures: object[]) =>
  ejs.renderFile(path.join(VIEWS, "asistente", "direccion.ejs"), {
    state: null,
    options: { effects: [], tellings: [], criteria: [], structures, forms: [], ingredients: [], hablas: [] },
    genres: [],
    estimateLabels: {},
    pasoActual: "direccion",
  });
const radios = (html: string) => [...html.matchAll(/<input type="radio" name="structure" value="(\w+)"([^>]*)>/g)];

describe("tres largos (Spec-750)", () => {
  it("«¿Qué tan largo?» ofrece Corto, Media y Larga, en ese orden y en tres columnas", async () => {
    const html = await direccion(LARGOS);
    expect(radios(html).map((m) => m[1])).toEqual(["corto", "medio", "largo"]);
    expect(html).toContain("Larga");
    expect(html).toContain("unos 35 minutos");
    expect(html).toMatch(/data-largo-opciones[\s\S]*sm:grid-cols-3/);
  });

  it("una historia nueva arranca en la media aunque no sea la primera", async () => {
    const elegida = radios(await direccion(LARGOS)).find((m) => /checked/.test(m[2]));
    expect(elegida?.[1]).toBe("medio");
  });

  it("con la media apagada, arranca en el primer largo que se puede escribir", async () => {
    const apagada = LARGOS.map((l) => (l.id === "medio" ? { ...l, disponible: false, nota: "n" } : l));
    const elegida = radios(await direccion(apagada)).find((m) => /checked/.test(m[2]));
    expect(elegida?.[1]).toBe("corto");
  });

  it("«El relato» marca la historia larga con un chip", async () => {
    const story = { id: "s-1", title: "La casa", status: "completed", structure: "largo" };
    const html = await ejs.renderFile(path.join(VIEWS, "relatos.ejs"), { story, relatos: [] });
    expect(html).toMatch(/data-larga>Larga</);
    const media = await ejs.renderFile(path.join(VIEWS, "relatos.ejs"), {
      story: { ...story, structure: "medio" },
      relatos: [],
    });
    expect(media).not.toContain("data-larga");
  });

  it("la galería marca la corta y la larga; la media va sin chip", async () => {
    const story = (id: string, structure: string) => ({
      id,
      title: id,
      status: "completed",
      structure,
      created_at: "2026-11-07T10:00:00.000Z",
    });
    const html = await ejs.renderFile(path.join(VIEWS, "gallery.ejs"), {
      rutas,
      stories: [story("c", "corto"), story("m", "medio"), story("l", "largo")],
    });
    expect(html.match(/data-corto>/g)).toHaveLength(1);
    expect(html.match(/data-larga>Larga/g)).toHaveLength(1);
  });
});
