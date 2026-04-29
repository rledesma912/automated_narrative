import { Request, Response } from "express";
import { getTheme } from "../services/theme.service";
import { renderPage } from "../utils/render";

const COOKIE = "nf_theme";
const MAX_AGE = 1000 * 60 * 60 * 24 * 365; // 1 año

export function setTheme(req: Request, res: Response): void {
  const requested = req.body?.theme ?? "horror";
  const { key } = getTheme(requested);
  res.cookie(COOKIE, key, { maxAge: MAX_AGE, httpOnly: true });
  const back = req.headers.referer ?? "/";
  res.redirect(back);
}

export async function componentsPage(_req: Request, res: Response): Promise<void> {
  await renderPage(res, "components", {
    title: "Componentes",
    activePage: "components",
  });
}
