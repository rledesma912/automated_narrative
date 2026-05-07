import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("axios");
vi.mock("../../../src/services/story.service", () => ({
  getStoryById: vi.fn(),
  getRelatosForStory: vi.fn(),
}));

import type { Request, Response } from "express";
import { relatosPage } from "../../../src/controllers/relatos.controller";
import { getStoryById, getRelatosForStory } from "../../../src/services/story.service";

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
