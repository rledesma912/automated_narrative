import { Request, Response } from "express";
import axios from "axios";
import { WizardData } from "../services/wizard.service";
import { mapWizardToCore } from "../services/mapper.service";
import { createStory, checkCoreHealth, streamUrl } from "../services/core_api.service";
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
  const coreStreamUrl = streamUrl(storyId);

  let story: Record<string, unknown> | null = null;
  let beats: unknown[] = [];

  try {
    const resp = await axios.get(`${CORE_API_URL}/api/v1/stories/${storyId}`, { timeout: 5000 });
    story = resp.data as Record<string, unknown>;

    if (story.status !== "processing") {
      const beatsResp = await axios.get(`${CORE_API_URL}/api/v1/stories/${storyId}/beats`, { timeout: 5000 });
      beats = Array.isArray(beatsResp.data) ? beatsResp.data : [];
    }
  } catch {
    // Story not found — SSE mode will handle connection error
  }

  const storyStatus = story ? String(story.status) : "processing";

  await renderPage(res, "streaming-room", {
    title: story ? String(story.title ?? "Historia") : "Generando historia...",
    activePage: "generate",
    storyId,
    coreStreamUrl,
    story,
    beats,
    storyStatus,
  });
}

export async function getActiveStreamApi(req: Request, res: Response): Promise<void> {
  const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";
  try {
    // Buscamos historias con estado 'processing' en la API Core
    const resp = await axios.get(`${CORE_API_URL}/api/v1/stories`, { timeout: 3000 });
    const stories = resp.data as any[];
    const activeStory = stories.find(s => s.status === "processing");

    // También pedimos el último evento del sistema
    const eventResp = await axios.get(`${CORE_API_URL}/api/v1/system/events?limit=1`, { timeout: 2000 });
    const lastEvent = eventResp.data[0] || null;

    res.json({ 
      active: !!activeStory, 
      story: activeStory || null,
      lastEvent: lastEvent
    });
  } catch {
    res.status(500).json({ error: "No se pudo consultar el estado de streaming" });
  }
}
