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

describe("streamingRoomPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("passes a relative path /api/v1/stories/:id/stream as coreStreamUrl", async () => {
    // axios.get se llama dos veces: para metadata y para beats
    (axios.get as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        data: { id: "abc-123", title: "Test", status: "completed" },
      })
      .mockResolvedValueOnce({ data: [] });

    const req = {
      params: { storyId: "abc-123" },
      query: {},
    } as unknown as Request;
    const res = {} as Response;

    await streamingRoomPage(req, res);

    expect(renderPage).toHaveBeenCalledTimes(1);
    const callArgs = (renderPage as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    const ctx = callArgs[2] as Record<string, unknown>;
    expect(ctx.coreStreamUrl).toBe("/api/v1/stories/abc-123/stream");
    // El path debe ser relativo: nada de localhost ni protocolo
    expect(String(ctx.coreStreamUrl)).not.toMatch(/^https?:/);
    expect(String(ctx.coreStreamUrl)).not.toMatch(/localhost|host\.docker/);
  });
});
