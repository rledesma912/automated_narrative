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

export async function exportStoryHandler(req: Request, res: Response): Promise<void> {
  const { storyId } = req.params;
  try {
    // Backend espera POST para exportar
    const resp = await axios.post(`${CORE_API_URL}/api/v1/stories/${storyId}/export`, {}, { timeout: 10000 });
    const { filename, content_b64 } = resp.data;

    if (!fs.existsSync(OUTPUT_DIR)) {
      fs.mkdirSync(OUTPUT_DIR, { recursive: true });
    }

    const filePath = path.join(OUTPUT_DIR, filename);
    fs.writeFileSync(filePath, Buffer.from(content_b64, 'base64'));

    // Actualizar path en DB para que la UI lo detecte
    await axios.patch(`${CORE_API_URL}/api/v1/stories/${storyId}/file-path`, { file_path: `output_stories/${filename}` });

    res.redirect("/galeria?success=export_ok");
  } catch (err) {
    console.error("Export error:", err);
    res.redirect("/galeria?error=export_failed");
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

export async function deleteMarkdownHandler(req: Request, res: Response): Promise<void> {
  const storyId = req.params["storyId"] as string;
  try {
    const resp = await axios.get(`${CORE_API_URL}/api/v1/stories/${storyId}`, { timeout: 3000 });
    const story = resp.data;

    if (story.file_path) {
      const filename = path.basename(story.file_path);
      const fullPath = path.join(OUTPUT_DIR, filename);
      if (fs.existsSync(fullPath)) {
        fs.unlinkSync(fullPath);
      }
      await updateFilePath(storyId, null);
    }

    if (req.headers["hx-request"]) {
      res.setHeader("HX-Redirect", "/galeria");
      res.status(200).send("");
    } else {
      res.redirect("/galeria");
    }
  } catch {
    res.status(500).send("Error al eliminar Markdown");
  }
}

export async function markdownCheckHandler(req: Request, res: Response): Promise<void> {
  const { storyId } = req.params;
  try {
    const resp = await axios.get(`${CORE_API_URL}/api/v1/stories/${storyId}`, { timeout: 3000 });
    const story = resp.data as Record<string, unknown>;

    if (!story.file_path) {
      res.send(
        `<form method="POST" action="/historia/${storyId}/exportar" class="inline">
          <button type="submit" class="text-sm text-forge-accent hover:opacity-70 flex items-center gap-2 bg-transparent border-none cursor-pointer p-0">
            <i data-lucide="download" class="w-4 h-4"></i> Exportar
          </button>
        </form>`,
      );
      return;
    }

    const filename = path.basename(story.file_path as string);
    const fullPath = path.join(OUTPUT_DIR, filename);
    if (fs.existsSync(fullPath)) {
      res.send(
        `<a href="/historia/${storyId}/ver-markdown" class="text-sm text-forge-muted hover:text-forge-accent flex items-center gap-2">
          <i data-lucide="file-text" class="w-4 h-4"></i> Markdown
        </a>`,
      );
    } else {
      res.send(
        `<button
          hx-get="/modales/confirmar-borrar-markdown/${storyId}"
          hx-target="body"
          hx-swap="beforeend"
          class="text-sm text-yellow-400 hover:opacity-70 flex items-center gap-2 bg-transparent border-none cursor-pointer p-0">
          <i data-lucide="file-x" class="w-4 h-4"></i> Desvincular
        </button>`,
      );
    }
  } catch {
    res.send("");
  }
}

export async function confirmDeleteModal(req: Request, res: Response): Promise<void> {
  const { storyId } = req.params;
  try {
    const resp = await axios.get(`${CORE_API_URL}/api/v1/stories/${storyId}`, { timeout: 3000 });
    res.render("partials/modal_confirm", {
      message: `¿Estás seguro de que deseas eliminar definitivamente la historia "${resp.data.title || "Sin título"}"?`,
      actionUrl: `/api/historia/${storyId}`,
      confirmText: "Eliminar Historia",
    });
  } catch {
    res.status(404).send("Historia no encontrada");
  }
}

export async function confirmDeleteMarkdownModal(req: Request, res: Response): Promise<void> {
  const { storyId } = req.params;
  res.render("partials/modal_confirm", {
    message: "¿Deseas eliminar únicamente el archivo Markdown exportado? La historia y su configuración se conservarán.",
    actionUrl: `/api/historia/${storyId}/markdown`,
    confirmText: "Eliminar Markdown",
  });
}

export async function verMarkdownHandler(req: Request, res: Response): Promise<void> {
  const { storyId } = req.params;
  try {
    const resp = await axios.get(`${CORE_API_URL}/api/v1/stories/${storyId}`, { timeout: 5000 });
    const story = resp.data;

    if (!story.file_path) {
      res.redirect(`/historia/${storyId}`);
      return;
    }

    const filename = path.basename(story.file_path);
    const fullPath = path.join(OUTPUT_DIR, filename);

    if (!fs.existsSync(fullPath)) {
      res.redirect(`/historia/${storyId}?error=file_not_found`);
      return;
    }

    const content = fs.readFileSync(fullPath, "utf-8");

    await renderPage(res, "visualizar_markdown", {
      title: `Ver: ${story.title}`,
      activePage: "gallery",
      story,
      content,
    });
  } catch {
    res.redirect("/galeria");
  }
}

export async function downloadMarkdownHandler(req: Request, res: Response): Promise<void> {
  const { storyId } = req.params;
  try {
    const resp = await axios.get(`${CORE_API_URL}/api/v1/stories/${storyId}`, { timeout: 5000 });
    const story = resp.data;

    if (!story.file_path) {
      res.redirect(`/historia/${storyId}`);
      return;
    }

    const filename = path.basename(story.file_path);
    const fullPath = path.join(OUTPUT_DIR, filename);

    if (!fs.existsSync(fullPath)) {
      res.redirect(`/historia/${storyId}?error=file_not_found`);
      return;
    }

    res.download(fullPath, filename);
  } catch {
    res.redirect("/galeria");
  }
}

export async function modalConfirmarRegenerar(req: Request, res: Response): Promise<void> {
  const { storyId } = req.params;
  res.render("partials/modal_regenerar", { layout: false, storyId });
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
