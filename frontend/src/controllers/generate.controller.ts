import { Request, Response } from "express";
import { renderPage } from "../utils/render";

export async function generatePage(_req: Request, res: Response): Promise<void> {
  await renderPage(res, "generate", {
    title: "Generar Historia",
    activePage: "generate",
  });
}
