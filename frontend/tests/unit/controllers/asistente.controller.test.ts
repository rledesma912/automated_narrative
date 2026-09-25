import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../../../src/services/authoring.service", () => ({
  getAuthoringOptions: vi.fn(),
  getAuthoringState: vi.fn(),
}));
vi.mock("../../../src/services/catalog.service", () => ({ getGenreCatalog: vi.fn() }));

import type { Request, Response } from "express";
import { asistentePage, nuevoPage } from "../../../src/controllers/asistente.controller";
import { getAuthoringOptions, getAuthoringState } from "../../../src/services/authoring.service";
import { getGenreCatalog } from "../../../src/services/catalog.service";

const OPTIONS = {
  effects: [{ id: "pavor", label: "Pavor creciente", detail: "Sube." }],
  tellings: [{ id: "caso", label: "Como un caso", detail: "«Mirá…»" }],
  criteria: [],
};
const STATE = {
  story_id: "s-1",
  status: "draft",
  direction: {
    title: "La pena", genero: "", subgenero: "", premise: "Algo pasa.", effect: "pavor",
    effect_other: "", ending: "", ending_intentional: false, telling: "caso",
    protagonist_name: "José", protagonist_role: "Chofer", narrator: "José", threat: null,
  },
  workshop: { round: 0, max_rounds: 5, finish: { kind: "sin_analizar", text: "", open_questions: 0 }, items: [] },
  outline: { acts: [], decisions: [] },
  characters: [{ name: "José", kind: "persona", relation: "" }],
  scenarios: [],
  active_job: null,
};

function res() {
  const r = {
    locals: {},
    status: vi.fn(),
    send: vi.fn(),
    redirect: vi.fn(),
    render: vi.fn((_view: string, locals: { body: string }) => {
      r.html = locals.body;
    }),
    html: "",
  };
  r.status.mockReturnValue(r);
  return r;
}

const req = (params: Record<string, string>) => ({ params }) as unknown as Request;

describe("asistente.controller (Spec-530 S4)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (getAuthoringOptions as ReturnType<typeof vi.fn>).mockResolvedValue(OPTIONS);
    (getGenreCatalog as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  });

  it("«Nuevo relato» renderiza la Dirección vacía, con Analizar deshabilitado", async () => {
    const r = res();
    await nuevoPage(req({}), r as unknown as Response);
    expect(r.html).toContain("¿Qué historia querés contar?");
    expect(r.html).toMatch(/data-analizar="consult"[^>]*disabled/);
    expect(r.html).toContain('data-story-id=""');
  });

  it("cada paso renderiza con el estado del Core", async () => {
    (getAuthoringState as ReturnType<typeof vi.fn>).mockResolvedValue(STATE);
    for (const [paso, texto] of [
      ["direccion", 'value="La pena"'],
      ["taller", "Todavía no analizaste la historia"],
      ["escaleta", "Todavía no hay escaleta"],
    ]) {
      const r = res();
      await asistentePage(req({ storyId: "s-1", paso }), r as unknown as Response);
      expect(r.html).toContain(texto);
      expect(r.html).toContain('data-story-id="s-1"');
    }
  });

  it("paso inexistente → 404; historia inexistente → galería", async () => {
    const r404 = res();
    await asistentePage(req({ storyId: "s-1", paso: "otro" }), r404 as unknown as Response);
    expect(r404.status).toHaveBeenCalledWith(404);

    (getAuthoringState as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("404"));
    const r = res();
    await asistentePage(req({ storyId: "nada", paso: "taller" }), r as unknown as Response);
    expect(r.redirect).toHaveBeenCalledWith("/galeria");
  });
});
