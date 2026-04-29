import { Request, Response } from "express";
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
  const { storyId } = req.params;
  const coreStreamUrl = streamUrl(storyId as string);

  await renderPage(res, "streaming-room", {
    title: "Generando historia...",
    activePage: "generate",
    storyId,
    coreStreamUrl,
  });
}
