import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock antes de importar el controller
vi.mock("axios");
vi.mock("../../../src/utils/render", () => ({
  renderPage: vi.fn(async () => undefined),
}));

import axios from "axios";
import { renderPage } from "../../../src/utils/render";
import { streamingRoomPage } from "../../../src/controllers/stream.controller";
import type { Request, Response } from "express";

const get = axios.get as unknown as ReturnType<typeof vi.fn>;

function notFound() {
  return Object.assign(new Error("404"), { isAxiosError: true, response: { status: 404 } });
}

async function render(query: Record<string, string> = {}) {
  const req = { params: { storyId: "abc-123" }, query } as unknown as Request;
  await streamingRoomPage(req, {} as Response);
  expect(renderPage).toHaveBeenCalledTimes(1);
  const callArgs = (renderPage as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
  return callArgs[2] as Record<string, unknown>;
}

/**
 * Spec-460 S4: la sala se entera de la generación en curso por el job activo
 * del Core (`GET /stories/:id/jobs/active`), no por `story.status`.
 */
describe("streamingRoomPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (axios.isAxiosError as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      (e: { isAxiosError?: boolean }) => !!e?.isAxiosError,
    );
  });

  it("con un job activo pasa su id y no carga beats", async () => {
    get
      .mockResolvedValueOnce({ data: { id: "abc-123", title: "T", status: "processing" } })
      .mockResolvedValueOnce({ data: { job_id: "job-1", status: "running" } });

    const ctx = await render();

    expect(ctx.activeJobId).toBe("job-1");
    expect(ctx.beats).toEqual([]);
    expect(get).toHaveBeenCalledTimes(2);
    expect(get.mock.calls[1][0]).toMatch(/\/api\/v1\/stories\/abc-123\/jobs\/active$/);
  });

  it("sin job activo carga los beats para el modo lectura", async () => {
    get
      .mockResolvedValueOnce({ data: { id: "abc-123", title: "T", status: "completed" } })
      .mockRejectedValueOnce(notFound())
      .mockResolvedValueOnce({ data: [{ number: 1, content: "x" }] });

    const ctx = await render();

    expect(ctx.activeJobId).toBeNull();
    expect(ctx.beats).toEqual([{ number: 1, content: "x" }]);
    expect(ctx.storyStatus).toBe("completed");
  });

  // Spec-660 D4: `?escribir=1` / `?regenerate=1` de links viejos no cambian nada.
  it.each([{ escribir: "1" }, { regenerate: "1" }, {}])("la sala no pregunta (%o)", async (query) => {
    get
      .mockResolvedValueOnce({ data: { id: "abc-123", title: "T", status: "draft" } })
      .mockRejectedValueOnce(notFound())
      .mockResolvedValueOnce({ data: [] });

    const ctx = await render(query);

    expect(ctx).not.toHaveProperty("startMode");
    expect(ctx).not.toHaveProperty("regenerateMode");
    expect(ctx.activeJobId).toBeNull();
  });

  it("no expone URLs del Core al template (Spec-221: el browser usa rutas relativas)", async () => {
    get
      .mockResolvedValueOnce({ data: { id: "abc-123", title: "T", status: "draft" } })
      .mockRejectedValueOnce(notFound())
      .mockResolvedValueOnce({ data: [] });

    const ctx = await render();

    expect(JSON.stringify(ctx)).not.toMatch(/https?:|localhost|host\.docker/);
  });
});
