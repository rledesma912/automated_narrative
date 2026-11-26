/**
 * Spec-795: el tablero, la bitácora visual del proyecto.
 *   GET /tablero            → las entregas, la más nueva arriba (?proyecto= filtra)
 *   GET /tablero/:id        → una entrega: qué mirar, sus imágenes y las opiniones
 */
import { Request, Response } from "express";
import axios from "axios";
import { randomUUID } from "crypto";
import { renderPage } from "../utils/render";
import { queMirarHtml } from "../utils/que_mirar";

const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";

/** Spec-795 D6: un id por navegador, en una cookie, para contar un voto por persona. */
export const COOKIE_NAVEGADOR = "forge_navegador";
const ID_VALIDO = /^[A-Za-z0-9-]{8,64}$/;

export function navegadorDe(req: Request, res: Response): string {
  const crudo = (req.headers.cookie ?? "")
    .split(";")
    .map((c) => c.trim().split("="))
    .find(([k]) => k === COOKIE_NAVEGADOR)?.[1];
  if (crudo && ID_VALIDO.test(crudo)) return crudo;
  const nuevo = randomUUID();
  res.cookie(COOKIE_NAVEGADOR, nuevo, { maxAge: 10 * 365 * 24 * 3600 * 1000, sameSite: "lax", path: "/" });
  return nuevo;
}

export async function tableroPage(req: Request, res: Response): Promise<void> {
  const proyecto = typeof req.query["proyecto"] === "string" ? req.query["proyecto"] : "";
  let datos: { proyectos: unknown[]; entregas: unknown[] } = { proyectos: [], entregas: [] };
  try {
    const r = await axios.get(`${CORE_API_URL}/api/v1/tablero/entregas`, {
      params: proyecto ? { proyecto } : {},
      timeout: 5000,
    });
    datos = r.data;
  } catch {
    // Backend offline: tablero vacío
  }
  res.setHeader("Cache-Control", "no-store");
  await renderPage(res, "tablero/index", {
    title: "Tablero",
    activePage: "tablero",
    proyectos: datos.proyectos,
    entregas: datos.entregas,
    proyecto,
  });
}

export async function entregaPage(req: Request, res: Response): Promise<void> {
  const id = String(req.params["id"]);
  const navegador = navegadorDe(req, res);
  try {
    const r = await axios.get(`${CORE_API_URL}/api/v1/tablero/entregas/${encodeURIComponent(id)}`, {
      params: { navegador },
      timeout: 5000,
    });
    res.setHeader("Cache-Control", "no-store");
    await renderPage(res, "tablero/entrega", {
      title: r.data.titulo,
      activePage: "tablero",
      entrega: r.data,
      queMirar: queMirarHtml(r.data.que_mirar),
    });
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      res.status(404).send("No encontramos esa entrega.");
      return;
    }
    console.error(`Error al abrir la entrega ${id}:`, error);
    res.status(500).send("No se pudo abrir la entrega.");
  }
}
