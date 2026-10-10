import { Request, Response } from "express";
import axios from "axios";
import { getActiveJob } from "../services/core_api.service";
import { renderPage } from "../utils/render";
import { actosDe } from "../utils/actos";

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
  // Spec-630 B14: `?escribir=1` (o el viejo `?regenerate=1`) pide arrancar: con un
  // relato terminado confirma «¿Regeneramos la historia?» (una versión nueva); con un borrador o uno fallido,
  // «¿Empezamos a escribir?». Sin eso, la sala solo muestra lo que hay.
  const pideEscribir = req.query["escribir"] === "1" || req.query["regenerate"] === "1";
  const regenerateMode = !activeJobId && pideEscribir && storyStatus === "completed";
  const startMode =
    !activeJobId && pideEscribir && (storyStatus === "draft" || storyStatus === "failed");

  await renderPage(res, "streaming-room", {
    title: story ? String(story.title ?? "Historia") : "Generando historia...",
    activePage: "generate",
    storyId,
    story,
    beats,
    storyStatus,
    regenerateMode,
    startMode,
    activeJobId,
    // Spec-650: los puntos de avance según el largo de la historia (5 o 3).
    actos: actosDe(story ? String(story.structure ?? "") : undefined),
  });
}
