import { Request, Response } from "express";
import { getStoryById, getRelatosForStory, getReadingSettings, getVideoScript, startActoRegeneration } from "../services/story.service";
import { splitActs } from "../utils/actos";
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

/** Spec-610 T1.4: corregir el relato acto por acto (§3.7.1). */
export const corregirRelatoPage = async (req: Request, res: Response) => {
  const storyId = req.params.storyId as string;
  const narrativeId = req.params.narrativeId as string;
  try {
    const story = await getStoryById(storyId);
    if (!story) return res.status(404).send("Historia no encontrada.");
    const relato = (await getRelatosForStory(storyId)).find((r) => r.id === narrativeId);
    if (!relato) return res.status(404).send("Relato no encontrado.");
    const actos = splitActs(relato.content);
    const lectura = await getReadingSettings();
    const acto = Math.min(Math.max(Number(req.query["acto"]) || 1, 1), Math.max(actos.length, 1));

    res.setHeader("Cache-Control", "no-store");
    await renderPage(res, "relatos/corregir", {
      story,
      relato,
      actos,
      lectura,
      actoInicial: acto,
      title: `Corregir «${story.title || "Sin título"}»`,
      activePage: "gallery",
    });
  } catch (error) {
    console.error(`Error al abrir la corrección de ${narrativeId}:`, error);
    res.status(500).send("No se pudo abrir el relato para corregir.");
  }
};

/** Spec-610 §3.7.2: «Para el video», el paquete de una variante (guion, calabaza, mapa). */
export const videoPage = async (req: Request, res: Response) => {
  const storyId = req.params.storyId as string;
  const narrativeId = req.params.narrativeId as string;
  try {
    const story = await getStoryById(storyId);
    if (!story) return res.status(404).send("Historia no encontrada.");
    const relato = (await getRelatosForStory(storyId)).find((r) => r.id === narrativeId);
    if (!relato) return res.status(404).send("Relato no encontrado.");
    const script = await getVideoScript(narrativeId);
    if (!script) return res.redirect(`/historia/${storyId}/relatos`);
    const actos = splitActs(relato.content).map((a) => ({
      number: a.number,
      name: a.name,
      parrafos: a.text.split(/\n[ \t]*\n+/).map((p) => p.trim()).filter(Boolean),
    }));
    res.setHeader("Cache-Control", "no-store");
    await renderPage(res, "relatos/video", {
      story,
      relato,
      script,
      actos,
      lectura: await getReadingSettings(),
      title: `Para el video: «${story.title || "Sin título"}»`,
      activePage: "gallery",
    });
  } catch (error) {
    console.error(`Error al abrir el paquete de ${narrativeId}:`, error);
    res.status(500).send("No se pudo abrir el guion para el video.");
  }
};
