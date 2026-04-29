import { Response } from "express";
import ejs from "ejs";
import path from "path";

const VIEWS = path.join(__dirname, "..", "views");

export async function renderPage(
  res: Response,
  page: string,
  locals: Record<string, unknown>
): Promise<void> {
  // Merge res.locals (theme vars, etc.) so partials can access them too
  const merged = { ...res.locals, ...locals };
  const body = await ejs.renderFile(path.join(VIEWS, `${page}.ejs`), merged);
  res.render("partials/layout", { ...merged, body });
}
