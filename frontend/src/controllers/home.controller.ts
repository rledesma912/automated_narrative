import { Request, Response } from "express";
import { renderPage } from "../utils/render";

export async function homePage(_req: Request, res: Response): Promise<void> {
  await renderPage(res, "home", {
    title: "Inicio",
    activePage: "home",
  });
}
