import { Request, Response } from "express";
import { getStoryById, getRelatosForStory } from "../services/story.service";
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
