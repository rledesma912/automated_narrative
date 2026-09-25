import { Request, Response } from "express";
import { renderPage } from "../utils/render";
import * as datos from "../maquetas/pena-del-colectivo";

/**
 * Spec-530 S0: maquetas navegables del asistente de autoría (Dirección, Taller,
 * Escaleta) con datos fijos. Solo se montan fuera de producción (ver app.ts).
 */
const PAGINAS = {
  direccion: "Dirección",
  taller: "Taller",
  escaleta: "Escaleta",
} as const;

type Pagina = keyof typeof PAGINAS;

export async function maquetaPage(req: Request, res: Response): Promise<void> {
  const pagina = req.params["pagina"] as Pagina;
  if (!(pagina in PAGINAS)) {
    res.status(404).send("Maqueta inexistente");
    return;
  }
  await renderPage(res, `maquetas/${pagina}`, {
    title: `Maqueta — ${PAGINAS[pagina]}`,
    activePage: "generate",
    pasoActual: pagina,
    ...datos,
  });
}
