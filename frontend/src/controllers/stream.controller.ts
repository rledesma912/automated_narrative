import { Request, Response } from "express";
import axios from "axios";
import { getActiveJob } from "../services/core_api.service";
import { renderPage } from "../utils/render";

export async function streamingRoomPage(req: Request, res: Response): Promise<void> {
  const { storyId } = req.params as { storyId: string };
  const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";

  let story: Record<string, unknown> | null = null;
  let beats: unknown[] = [];
  let activeJobId: string | null = null;

  try {
    const resp = await axios.get(`${CORE_API_URL}/api/v1/stories/${storyId}`, { timeout: 5000 });
    story = resp.data as Record<string, unknown>;
    // Spec-460: "hay una generación en curso" lo dice el job, no story.status.
    activeJobId = (await getActiveJob(storyId))?.job_id ?? null;
    if (!activeJobId) {
      const beatsResp = await axios.get(`${CORE_API_URL}/api/v1/stories/${storyId}/beats`, { timeout: 5000 });
      beats = Array.isArray(beatsResp.data) ? beatsResp.data : [];
    }
  } catch {
    // Historia inexistente o Core caído: la sala muestra el modo lectura vacío.
  }

  const storyStatus = story ? String(story.status) : "draft";
  const regenerateMode =
    !activeJobId && req.query["regenerate"] === "1" && storyStatus === "completed";

  await renderPage(res, "streaming-room", {
    title: story ? String(story.title ?? "Historia") : "Generando historia...",
    activePage: "generate",
    storyId,
    story,
    beats,
    storyStatus,
    regenerateMode,
    activeJobId,
  });
}
