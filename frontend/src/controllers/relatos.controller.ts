import { Request, Response } from "express";
import { getStoryById, getRelatosForStory, startActoRegeneration } from "../services/story.service";
import { renderPage } from "../utils/render";

export const relatosPage = async (req: Request, res: Response) => {
  const storyId = req.params.storyId as string;

  try {
    const story = await getStoryById(storyId);
    if (!story) {
      return res.status(404).send("Historia no encontrada.");
    }

    const relatos = await getRelatosForStory(storyId);

    res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
    res.setHeader('Pragma', 'no-cache');
    res.setHeader('Expires', '0');

    await renderPage(res, "relatos", {
      story,
      relatos,
      title: `Relatos de "${story.title || 'Sin título'}"`,
      activePage: "gallery",
    });
  } catch (error) {
    console.error("Error al cargar la página de relatos:", error);
    res.status(500).send("Error interno del servidor.");
  }
};

async function renderRelatoPanel(
  res: Response,
  storyId: string,
  narrativeId: string,
  extra: { regenerating?: { acto: number; jobId: string }; panelError?: string } = {},
) {
  const story = await getStoryById(storyId);
  if (!story) return res.status(404).send("Historia no encontrada.");
  const relato = (await getRelatosForStory(storyId)).find((r) => r.id === narrativeId);
  if (!relato) return res.status(404).send("Relato no encontrado.");

  res.render("partials/relato_panel", {
    story,
    relato,
    displayTitle: relato.title || "Relato",
    isActive: true,
    regenerating: extra.regenerating ?? null,
    panelError: extra.panelError ?? null,
  });
}

/**
 * Regenera la Voz de un acto (Spec-430) como job (Spec-460 S7): responde al
 * instante con el panel en estado "Regenerando acto N"; cuando el job termina,
 * generation-guard.js recarga el panel con `relatoPanelFragment`.
 */
export const regenerarActoAction = async (req: Request, res: Response) => {
  const storyId = req.params.storyId as string;
  const narrativeId = req.params.narrativeId as string;
  const acto = Number(req.params.actoNumero);

  try {
    const start = await startActoRegeneration(storyId, narrativeId, acto);
    if (start.status === 202 && start.jobId) {
      return await renderRelatoPanel(res, storyId, narrativeId, {
        regenerating: { acto, jobId: start.jobId },
      });
    }
    const panelError =
      start.status === 409
        ? "Ya hay una generación en curso para esta historia. Esperá a que termine."
        : start.detail ?? "No se pudo regenerar el acto.";
    return await renderRelatoPanel(res, storyId, narrativeId, { panelError });
  } catch (error) {
    console.error(`Error al regenerar acto ${acto} de ${storyId}:`, error);
    res.status(500).send("No se pudo regenerar el acto. Intentá de nuevo.");
  }
};

/** Fragmento del panel de un relato (recarga tras regenerar un acto). `?error=` lo muestra. */
export const relatoPanelFragment = async (req: Request, res: Response) => {
  const storyId = req.params.storyId as string;
  const narrativeId = req.params.narrativeId as string;
  const error = req.query["error"];
  try {
    await renderRelatoPanel(res, storyId, narrativeId, {
      panelError: typeof error === "string" && error ? `No se pudo regenerar el acto: ${error}` : undefined,
    });
  } catch (err) {
    console.error(`Error al cargar el panel ${narrativeId}:`, err);
    res.status(500).send("No se pudo cargar el relato.");
  }
};
