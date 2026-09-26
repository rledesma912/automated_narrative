import { Request, Response } from "express";
import { renderPage } from "../utils/render";
import { getGenreCatalog } from "../services/catalog.service";
import { getAuthoringOptions, getAuthoringState } from "../services/authoring.service";

/**
 * Spec-530 S4: vistas del asistente de autoría (Dirección, Taller, Escaleta).
 * Se renderizan con el estado del Core; guardar y pedirle cosas a la IA lo hace
 * el navegador (public/js/asistente.js) contra /api.
 */
const PASOS = ["direccion", "taller", "escaleta"] as const;
type Paso = (typeof PASOS)[number];

const TITULOS: Record<Paso, string> = {
  direccion: "Dirección",
  taller: "Taller",
  escaleta: "Escaleta",
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
