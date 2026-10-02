import { Request, Response } from "express";
import ejs from "ejs";
import path from "path";
import axios from "axios";
import { renderPage } from "../utils/render";
import { getGenreCatalog } from "../services/catalog.service";
import { getAuthoringOptions, getAuthoringState } from "../services/authoring.service";

/**
 * Spec-530 S4: vistas del asistente de autoría (Tu idea, Preguntas, Los actos; Spec-580).
 * Se renderizan con el estado del Core; guardar y pedirle cosas a la IA lo hace
 * el navegador (public/js/asistente.js) contra /api.
 */
const PASOS = ["direccion", "taller", "escaleta"] as const;
type Paso = (typeof PASOS)[number];

const TITULOS: Record<Paso, string> = {
  direccion: "Tu idea",
  taller: "Preguntas",
  escaleta: "Los actos",
};

export async function nuevoPage(_req: Request, res: Response): Promise<void> {
  const [options, genres] = await Promise.all([getAuthoringOptions(), getGenreCatalog()]);
  await renderPage(res, "asistente/direccion", {
    title: "Nuevo relato",
    activePage: "generate",
    pasoActual: "direccion",
    state: null,
    options,
    genres: genres ?? [],
  });
}

export async function asistentePage(req: Request, res: Response): Promise<void> {
  const storyId = req.params["storyId"] as string;
  const paso = req.params["paso"] as Paso;
  if (!PASOS.includes(paso)) {
    res.status(404).send("Paso inexistente");
    return;
  }
  let state;
  try {
    state = await getAuthoringState(storyId);
  } catch {
    res.redirect("/galeria");
    return;
  }
  const [options, genres] = await Promise.all([
    getAuthoringOptions(),
    paso === "direccion" ? getGenreCatalog() : Promise.resolve(null),
  ]);
  await renderPage(res, `asistente/${paso}`, {
    title: `${TITULOS[paso]} — ${state.direction.title}`,
    activePage: "generate",
    pasoActual: paso,
    state,
    options,
    genres: genres ?? [],
  });
}

/**
 * Spec-630 S2 (B5): el contenido de un paso, sin layout, para que asistente.js
 * reemplace solo lo que cambió (sin recargar ni mover el scroll). «Los actos»
 * devuelve el resumen y las tarjetas; «Preguntas», todo su contenido (responder
 * mueve una pregunta de «Te falta contarme» a «Ya lo tenés»).
 */
const FRAGMENTOS: Record<string, string> = {
  escaleta: "asistente/_escaleta_contenido",
  taller: "asistente/_taller_contenido",
};

export async function fragmentoAsistente(req: Request, res: Response): Promise<void> {
  const storyId = req.params["storyId"] as string;
  const view = FRAGMENTOS[req.params["paso"] as string];
  if (!view) {
    res.status(404).send("Paso inexistente");
    return;
  }
  let state;
  try {
    state = await getAuthoringState(storyId);
  } catch (err) {
    const notFound = axios.isAxiosError(err) && err.response?.status === 404;
    res.status(notFound ? 404 : 502).send(notFound ? "Historia inexistente" : "El Core no responde");
    return;
  }
  const html = await ejs.renderFile(path.join(__dirname, "..", "views", `${view}.ejs`), {
    ...(res.app?.locals ?? {}),
    ...res.locals,
    state,
  });
  res.setHeader("Cache-Control", "no-store");
  res.type("html").send(html);
}
