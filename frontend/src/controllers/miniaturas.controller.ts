/**
 * Spec-790 §10.7: la sección «Miniaturas».
 *   GET /miniaturas            → las historias, con un chip si ya tienen miniatura
 *   GET /miniaturas/:storyId   → el formulario (¿quién va?, bocetos, el lugar, el color) y las 4
 */
import { Request, Response } from "express";
import axios from "axios";
import { renderPage } from "../utils/render";

const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";

export async function miniaturasPage(_req: Request, res: Response): Promise<void> {
  let stories: Array<Record<string, unknown>> = [];
  let conMiniatura: string[] = [];
  try {
    const [s, t] = await Promise.all([
      axios.get(`${CORE_API_URL}/api/v1/stories`, { timeout: 5000 }),
      axios.get(`${CORE_API_URL}/api/v1/thumbnails`, { timeout: 5000 }),
    ]);
    stories = Array.isArray(s.data) ? s.data : [];
    conMiniatura = t.data?.story_ids ?? [];
  } catch {
    // Backend offline: lista vacía
  }
  await renderPage(res, "miniaturas/index", {
    title: "Miniaturas",
    activePage: "miniaturas",
    stories,
    conMiniatura,
  });
}

export async function miniaturaPage(req: Request, res: Response): Promise<void> {
  const storyId = String(req.params["storyId"]);
  try {
    const [s, t] = await Promise.all([
      axios.get(`${CORE_API_URL}/api/v1/stories/${storyId}`, { timeout: 5000 }),
      axios.get(`${CORE_API_URL}/api/v1/stories/${storyId}/thumbnail`, { timeout: 5000 }),
    ]);
    res.setHeader("Cache-Control", "no-store");
    await renderPage(res, "miniaturas/historia", {
      title: `Miniatura: «${s.data.title || "Sin título"}»`,
      activePage: "miniaturas",
      story: s.data,
      thumb: t.data,
      bust: Date.now(),
    });
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      res.status(404).send("Historia no encontrada.");
      return;
    }
    console.error(`Error al abrir la miniatura de ${storyId}:`, error);
    res.status(500).send("No se pudo abrir la miniatura.");
  }
}
