import { Request, Response } from "express";
import { getStoryById, getRelatosForStory, regenerateActoVoz } from "../services/story.service";
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

/** Regenera solo la Voz de un acto puntual y re-renderiza el panel del relato (Spec-430). */
export const regenerarActoAction = async (req: Request, res: Response) => {
  const storyId = req.params.storyId as string;
  const narrativeId = req.params.narrativeId as string;
  const actoNumero = req.params.actoNumero as string;

  try {
    await regenerateActoVoz(storyId, narrativeId, Number(actoNumero));

    const story = await getStoryById(storyId);
    if (!story) {
      return res.status(404).send("Historia no encontrada.");
    }

    const relatos = await getRelatosForStory(storyId);
    const relato = relatos.find((r) => r.id === narrativeId);
    if (!relato) {
      return res.status(404).send("Relato no encontrado.");
    }

    res.render("partials/relato_panel", {
      story,
      relato,
      displayTitle: relato.title || "Relato",
      isActive: true,
    });
  } catch (error) {
    console.error(`Error al regenerar acto ${actoNumero} de ${storyId}:`, error);
    res.status(500).send("No se pudo regenerar el acto. Intentá de nuevo.");
  }
};
