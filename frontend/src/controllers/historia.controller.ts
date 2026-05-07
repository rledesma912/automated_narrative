import { Request, Response } from "express";
import axios from "axios";
import fs from "fs";
import path from "path";
import { renderPage } from "../utils/render";
import { checkCoreHealth, deleteStory, updateFilePath } from "../services/core_api.service";

const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";
const OUTPUT_DIR = process.env.OUTPUT_STORIES_DIR ?? path.join(__dirname, "../../public/output_stories");

export async function historiaPage(req: Request, res: Response): Promise<void> {
  const { storyId } = req.params;
  const startParam = req.query.start as string;
  const startGeneration = startParam === "1" ? 1 : 0;

  try {
    const resp = await axios.get(`${CORE_API_URL}/api/v1/stories/${storyId}`, { timeout: 5000 });
    await renderPage(res, "historia", {
      title: resp.data.title ?? "Historia",
      activePage: "gallery",
      story: resp.data,
      pageError: req.query.error ?? null,
      startGeneration,
    });
  } catch {
    res.redirect("/galeria");
  }
}

export async function generateNarrativeHandler(req: Request, res: Response): Promise<void> {
  const { storyId } = req.params;
  try {
    const title = `Relato ${new Date().toLocaleString('es-AR')}`;
    const resp = await axios.post(
      `${CORE_API_URL}/api/v1/story-templates/${storyId}/generate-narrative?title=${encodeURIComponent(title)}`,
      {},
      { timeout: 30000 },
    );
    res.redirect(`/historia/${storyId}?success=narrative_generated`);
  } catch (err) {
    console.error("Generate narrative error:", err);
    res.redirect(`/historia/${storyId}?error=narrative_failed`);
  }
}

export async function listNarrativesHandler(req: Request, res: Response): Promise<void> {
  const { storyId } = req.params;
  try {
    const resp = await axios.get(`${CORE_API_URL}/api/v1/story-templates/${storyId}/narratives`, { timeout: 5000 });
    res.json(resp.data);
  } catch {
    res.status(500).json({ error: "Error al listar narrativas" });
  }
}

export async function deleteStoryHandler(req: Request, res: Response): Promise<void> {
  const storyId = req.params["storyId"] as string;
  try {
    const resp = await axios.get(`${CORE_API_URL}/api/v1/stories/${storyId}`, { timeout: 3000 });
    const story = resp.data;

    await deleteStory(storyId);

    if (story.file_path) {
      const filename = path.basename(story.file_path);
      const fullPath = path.join(OUTPUT_DIR, filename);
      if (fs.existsSync(fullPath)) {
        fs.unlinkSync(fullPath);
      }
    }

    if (req.headers["hx-request"]) {
      res.setHeader("HX-Redirect", "/galeria");
      res.status(200).send("");
    } else {
      res.redirect("/galeria");
    }
  } catch (err: unknown) {
    res.status(500).send("Error al eliminar");
  }
}

export async function confirmDeleteModal(req: Request, res: Response): Promise<void> {
  const { storyId } = req.params;
  try {
    const resp = await axios.get(`${CORE_API_URL}/api/v1/stories/${storyId}`, { timeout: 3000 });
    res.render("partials/modal_confirm", {
      message: `¿Estás seguro de que deseas eliminar definitivamente la historia "${resp.data.title || "Sin título"}"?`,
      actionUrl: `/internal/historia/${storyId}`,
      confirmText: "Eliminar Historia",
    });
  } catch {
    res.status(404).send("Historia no encontrada");
  }
}

function htmxRedirect(res: Response, req: import("express").Request, url: string): void {
  if (req.headers["hx-request"] === "true") {
    res.setHeader("HX-Redirect", url);
    res.status(200).send("");
  } else {
    res.redirect(url);
  }
}

export async function generarDesdeHistoria(req: Request, res: Response): Promise<void> {
  const { storyId } = req.params;

  const health = await checkCoreHealth();
  if (!health.reachable || (health.status !== "healthy" && health.status !== "degraded")) {
    htmxRedirect(res, req, "/debug?error=backend_offline");
    return;
  }

  // Spec-219: si la historia está completed, no patchear ahora — dejar que la sala
  // muestre la pantalla de regeneración con advertencia y dispare el PATCH desde JS
  // cuando el usuario confirme. Mantiene la regeneración no destructiva.
  let currentStatus = "";
  try {
    const resp = await axios.get(`${CORE_API_URL}/api/v1/stories/${storyId}`, { timeout: 5000 });
    currentStatus = String((resp.data as { status?: string })?.status ?? "");
  } catch (err: any) {
    const detail = err?.response?.data?.detail ?? err?.message ?? "unknown";
    htmxRedirect(res, req, `/debug?error=regeneration_failed&detail=${encodeURIComponent(detail)}`);
    return;
  }

  if (currentStatus === "completed") {
    htmxRedirect(res, req, `/generar/stream/${storyId}?regenerate=1`);
    return;
  }

  try {
    await axios.patch(
      `${CORE_API_URL}/api/v1/stories/${storyId}/status`,
      { status: "processing" },
      { timeout: 5000 },
    );
  } catch (err: any) {
    const detail = err?.response?.data?.detail ?? err?.message ?? "unknown";
    htmxRedirect(res, req, `/debug?error=regeneration_failed&detail=${encodeURIComponent(detail)}`);
    return;
  }

  htmxRedirect(res, req, `/generar/stream/${storyId}`);
}

export async function updateFilePathHandler(req: Request, res: Response): Promise<void> {
  const storyId = req.params.storyId as string;
  try {
    await updateFilePath(storyId, null);
    res.status(200).json({ success: true });
  } catch {
    res.status(500).json({ error: "Error al desvincular" });
  }
}
