import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("axios");
vi.mock("../../../src/services/story.service", () => ({
  getStoryById: vi.fn(),
  getRelatosForStory: vi.fn(),
  startActoRegeneration: vi.fn(),
}));

import type { Request, Response } from "express";
import {
  relatosPage,
  regenerarActoAction,
  relatoPanelFragment,
} from "../../../src/controllers/relatos.controller";
import {
  getStoryById,
  getRelatosForStory,
  startActoRegeneration,
} from "../../../src/services/story.service";

describe("relatosPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the relatos page wrapped in the standard layout (Spec-316)", async () => {
    (getStoryById as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "story-1",
      title: "La casa",
    });
    (getRelatosForStory as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
      {
        id: "n-1",
        story_template_id: "story-1",
        title: "Relato 1",
        content: "Contenido 1",
        status: "completed",
        created_at: "2026-05-05T10:00:00.000Z",
      },
    ]);

    const render = vi.fn();
    const setHeader = vi.fn();
    const req = { params: { storyId: "story-1" } } as unknown as Request;
    const res = {
      render,
      setHeader,
      locals: { themeCssVars: "", themeFont: "serif", activeTheme: "default", allThemes: [] },
    } as unknown as Response;

    await relatosPage(req, res);

    expect(getStoryById).toHaveBeenCalledWith("story-1");
    expect(getRelatosForStory).toHaveBeenCalledWith("story-1");
    expect(render).toHaveBeenCalledTimes(1);

    const [view, locals] = render.mock.calls[0] as [string, Record<string, unknown>];
    expect(view).toBe("partials/layout");
    expect(locals.story).toEqual({ id: "story-1", title: "La casa" });
    expect(locals.relatos).toHaveLength(1);
    expect(locals.activePage).toBe("gallery");
    expect(locals.title).toBe('Relatos de "La casa"');
    expect(typeof locals.body).toBe("string");
  });

  it("returns 404 when the story does not exist", async () => {
    (getStoryById as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(null);

    const status = vi.fn().mockReturnThis();
    const send = vi.fn();
    const req = { params: { storyId: "missing" } } as unknown as Request;
    const res = { status, send } as unknown as Response;

    await relatosPage(req, res);

    expect(status).toHaveBeenCalledWith(404);
    expect(send).toHaveBeenCalledWith("Historia no encontrada.");
    expect(getRelatosForStory).not.toHaveBeenCalled();
  });
});


// ── Spec-460 S7: regenerar un acto es un job ────────────────────────────────

function mockStoryWithRelato() {
  (getStoryById as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ id: "s-1", title: "T" });
  (getRelatosForStory as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
    { id: "n-1", story_template_id: "s-1", title: "Relato", content: "## Beat 1\n\nx" },
  ]);
}

function panelRes() {
  const render = vi.fn();
  const res = { render, status: vi.fn(), send: vi.fn() } as unknown as Response;
  (res.status as unknown as ReturnType<typeof vi.fn>).mockReturnValue(res);
  return { res, render };
}

const regenReq = {
  params: { storyId: "s-1", narrativeId: "n-1", actoNumero: "3" },
} as unknown as Request;

describe("regenerarActoAction", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStoryWithRelato();
  });

  it("lanza el job y devuelve el panel en estado 'regenerando' al instante", async () => {
    (startActoRegeneration as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      status: 202,
      jobId: "job-7",
      detail: null,
    });
    const { res, render } = panelRes();

    await regenerarActoAction(regenReq, res);

    expect(startActoRegeneration).toHaveBeenCalledWith("s-1", "n-1", 3);
    const [view, locals] = render.mock.calls[0] as [string, Record<string, unknown>];
    expect(view).toBe("partials/relato_panel");
    expect(locals.regenerating).toEqual({ acto: 3, jobId: "job-7" });
    expect(locals.panelError).toBeNull();
  });

  it("con otra generación en curso (409) muestra el aviso en el panel", async () => {
    (startActoRegeneration as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      status: 409,
      jobId: "job-1",
      detail: null,
    });
    const { res, render } = panelRes();

    await regenerarActoAction(regenReq, res);

    const locals = render.mock.calls[0]![1] as Record<string, unknown>;
    expect(locals.regenerating).toBeNull();
    expect(String(locals.panelError)).toMatch(/generación en curso/);
  });

  it("un rechazo de validación muestra el detalle del Core", async () => {
    (startActoRegeneration as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      status: 422,
      jobId: null,
      detail: "El acto 3 no está narrado",
    });
    const { res, render } = panelRes();

    await regenerarActoAction(regenReq, res);

    expect((render.mock.calls[0]![1] as Record<string, unknown>).panelError).toBe(
      "El acto 3 no está narrado",
    );
  });
});

describe("relatoPanelFragment", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStoryWithRelato();
  });

  it("devuelve el panel actualizado", async () => {
    const { res, render } = panelRes();

    await relatoPanelFragment(
      { params: { storyId: "s-1", narrativeId: "n-1" }, query: {} } as unknown as Request,
      res,
    );

    const locals = render.mock.calls[0]![1] as Record<string, unknown>;
    expect(locals.isActive).toBe(true);
    expect(locals.panelError).toBeNull();
  });

  it("con ?error= muestra por qué falló la regeneración", async () => {
    const { res, render } = panelRes();

    await relatoPanelFragment(
      {
        params: { storyId: "s-1", narrativeId: "n-1" },
        query: { error: "Ollama caído" },
      } as unknown as Request,
      res,
    );

    expect((render.mock.calls[0]![1] as Record<string, unknown>).panelError).toBe(
      "No se pudo regenerar el acto: Ollama caído",
    );
  });
});
