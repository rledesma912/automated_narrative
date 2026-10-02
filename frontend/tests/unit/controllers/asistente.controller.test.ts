import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../../../src/services/authoring.service", () => ({
  getAuthoringOptions: vi.fn(),
  getAuthoringState: vi.fn(),
}));
vi.mock("../../../src/services/catalog.service", () => ({ getGenreCatalog: vi.fn() }));

import type { Request, Response } from "express";
import { readFileSync } from "fs";
import path from "path";
import { asistentePage, fragmentoAsistente, nuevoPage } from "../../../src/controllers/asistente.controller";
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
      ["taller", "Todavía no hay preguntas"],
      ["escaleta", "Todavía no armaste los actos"],
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

/** Spec-630 S2 T2.2: el contenido de un paso, sin layout, para actualizar sin recargar. */
describe("fragmentoAsistente", () => {
  const FIXTURE = JSON.parse(
    readFileSync(path.join(process.cwd(), "tests/fixtures/asistente/estado.json"), "utf8"),
  );

  function fragRes() {
    const r = {
      locals: {},
      body: "",
      statusCode: 200,
      setHeader: vi.fn(),
      status: vi.fn((c: number) => ((r.statusCode = c), r)),
      type: vi.fn(() => r),
      send: vi.fn((b: string) => ((r.body = b), r)),
    };
    return r;
  }

  beforeEach(() => vi.clearAllMocks());

  it("«Los actos»: el resumen y las cinco tarjetas, sin layout ni barra", async () => {
    (getAuthoringState as ReturnType<typeof vi.fn>).mockResolvedValue(FIXTURE);
    const r = fragRes();
    await fragmentoAsistente(req({ storyId: "s-1", paso: "escaleta" }), r as unknown as Response);
    expect(r.body).toContain("data-resumen-actos");
    expect(r.body.match(/data-acto="\d"/g)).toEqual(["1", "2", "3", "4", "5"].map((n) => `data-acto="${n}"`));
    expect(r.body).not.toContain("<html");
    expect(r.body).not.toContain("asistente-barra");
    expect(r.setHeader).toHaveBeenCalledWith("Cache-Control", "no-store");
  });

  it("«Preguntas»: lo que falta y lo que ya está", async () => {
    (getAuthoringState as ReturnType<typeof vi.fn>).mockResolvedValue(FIXTURE);
    const r = fragRes();
    await fragmentoAsistente(req({ storyId: "s-1", paso: "taller" }), r as unknown as Response);
    expect(r.body).toContain("Te falta contarme");
    expect(r.body).toContain("Ya lo tenés");
    expect(r.body).toContain('data-pregunta="meta"');
    expect(r.body).not.toContain("asistente-barra");
  });

  it("paso inexistente → 404; historia inexistente → 404; Core caído → 502", async () => {
    const r1 = fragRes();
    await fragmentoAsistente(req({ storyId: "s-1", paso: "direccion" }), r1 as unknown as Response);
    expect(r1.statusCode).toBe(404);

    (getAuthoringState as ReturnType<typeof vi.fn>).mockRejectedValue(
      Object.assign(new Error("404"), { isAxiosError: true, response: { status: 404 } }),
    );
    const r2 = fragRes();
    await fragmentoAsistente(req({ storyId: "nada", paso: "escaleta" }), r2 as unknown as Response);
    expect(r2.statusCode).toBe(404);

    (getAuthoringState as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("ECONNREFUSED"));
    const r3 = fragRes();
    await fragmentoAsistente(req({ storyId: "s-1", paso: "escaleta" }), r3 as unknown as Response);
    expect(r3.statusCode).toBe(502);
  });
});
