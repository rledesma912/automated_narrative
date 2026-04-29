import { Request, Response } from "express";
import axios from "axios";
import { renderPage } from "../utils/render";

const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";

export async function galleryPage(_req: Request, res: Response): Promise<void> {
  let stories: unknown[] = [];
  try {
    const resp = await axios.get(`${CORE_API_URL}/api/v1/stories`, { timeout: 5000 });
    stories = Array.isArray(resp.data) ? resp.data : [];
  } catch {
    // Backend offline — mostrar galería vacía sin error
  }

  await renderPage(res, "gallery", {
    title: "Galería",
    activePage: "gallery",
    stories,
  });
}
