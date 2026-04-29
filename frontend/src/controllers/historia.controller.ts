import { Request, Response } from "express";
import axios from "axios";
import { renderPage } from "../utils/render";
import { checkCoreHealth } from "../services/core_api.service";

const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";

export async function historiaPage(req: Request, res: Response): Promise<void> {
  const { storyId } = req.params;
  try {
    const resp = await axios.get(`${CORE_API_URL}/api/v1/stories/${storyId}`, { timeout: 5000 });
    await renderPage(res, "historia", {
      title: resp.data.title ?? "Historia",
      activePage: "gallery",
      story: resp.data,
    });
  } catch {
    res.redirect("/galeria");
  }
}

export async function generarDesdeHistoria(req: Request, res: Response): Promise<void> {
  const { storyId } = req.params;

  const health = await checkCoreHealth();
  if (!health.reachable || health.status !== "healthy") {
    res.redirect("/debug?error=backend_offline");
    return;
  }

  try {
    // Marcar la historia como pending para que el stream la genere
    await axios.patch(
      `${CORE_API_URL}/api/v1/stories/${storyId}/status`,
      { status: "pending" },
      { timeout: 5000 },
    );
  } catch {
    // Si no existe el endpoint PATCH, continuar igual — el stream lo tomará
  }

  res.redirect(`/generar/stream/${storyId}`);
}
