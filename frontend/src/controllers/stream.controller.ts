import { Request, Response } from "express";
import axios from "axios";
import { WizardData } from "../services/wizard.service";
import { mapWizardToCore } from "../services/mapper.service";
import {
  createStory,
  checkCoreHealth,
  getActiveJob,
  startGeneration,
} from "../services/core_api.service";
import { renderPage } from "../utils/render";

type WizardSession = Request["session"] & { wizard?: WizardData };

export async function submitGeneration(req: Request, res: Response): Promise<void> {
  const action = (req.body as Record<string, string>)["action"] ?? "generate";

  // Solo verificar salud si vamos a generar
  if (action === "generate") {
    const health = await checkCoreHealth();
    if (!health.reachable || health.status !== "healthy") {
      res.redirect("/debug?error=backend_offline");
      return;
    }
  }

  const wizard = (req.session as WizardSession).wizard ?? {};
  const coreDto = mapWizardToCore(wizard);

  try {
    const story = await createStory(
      coreDto as unknown as Record<string, unknown>,
      action,
    );

    if (action === "save") {
      const isAjax = req.query["format"] === "json";
      if (isAjax) {
        res.json({ id: story.id });
        return;
      }
      res.redirect(`/historia/${story.id}`);
    } else {
      // Spec-460: la generación arranca como job en el servidor; la sala se ata.
      await startGeneration(story.id);
      res.redirect(`/generar/stream/${story.id}`);
    }
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    res.redirect(`/generar/confirmar?error=${encodeURIComponent(msg)}`);
  }
}

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
