import { Request, Response } from "express";
import axios from "axios";
import { deleteStory, getActiveJob } from "../services/core_api.service";
import { editarHref } from "../utils/rutas";

const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";

/**
 * Spec-630 B12: la ficha de la historia ya no existe. Los links viejos llevan a
 * «Los actos» o, si hay un relato escribiéndose, a la sala que lo muestra.
 */
export async function historiaRedirect(req: Request, res: Response): Promise<void> {
  const storyId = String(req.params["storyId"]);
  let job = null;
  try {
    job = await getActiveJob(storyId);
  } catch {
    /* Core caído: igual se puede abrir la edición, que avisa por su cuenta */
  }
  if (job && job.kind === "full_generation") {
    res.redirect(`/generar/stream/${encodeURIComponent(storyId)}`);
    return;
  }
  res.redirect(editarHref(storyId));
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
    await deleteStory(storyId);

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

/**
 * Spec-660 D2: escribir se pregunta donde se toca el botón (escribir-relato.js). Este
 * POST queda solo para pestañas o links viejos y lleva a la sala, sin lanzar nada.
 */
export async function generarDesdeHistoria(req: Request, res: Response): Promise<void> {
  htmxRedirect(res, req, `/generar/stream/${String(req.params["storyId"])}`);
}
