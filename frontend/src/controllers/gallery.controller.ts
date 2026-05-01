import { Request, Response } from "express";
import axios from "axios";
import { renderPage } from "../utils/render";

const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";

const FLASH_MESSAGES: Record<string, string> = {
  export_ok:     "Markdown generado correctamente.",
  export_failed: "No se pudo generar el Markdown. Intenta de nuevo.",
  load_failed:   "No se pudo cargar la historia.",
};

export async function galleryPage(req: Request, res: Response): Promise<void> {
  let stories: unknown[] = [];
  try {
    const resp = await axios.get(`${CORE_API_URL}/api/v1/stories`, { timeout: 5000 });
    stories = Array.isArray(resp.data) ? resp.data : [];
  } catch {
    // Backend offline — mostrar galería vacía sin error
  }

  const flashKey = (req.query["success"] ?? req.query["error"]) as string | undefined;
  const flashType = req.query["success"] ? "success" : req.query["error"] ? "error" : null;

  await renderPage(res, "gallery", {
    title: "Galería",
    activePage: "gallery",
    stories,
    flashMsg:  flashKey ? (FLASH_MESSAGES[flashKey] ?? null) : null,
    flashType,
  });
}
