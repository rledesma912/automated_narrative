import { Request, Response, NextFunction } from "express";
import { getTheme, allThemes, toCssVars } from "../services/theme.service";

const COOKIE = "nf_theme";

export function themeMiddleware(req: Request, res: Response, next: NextFunction): void {
  const { key, def } = getTheme(req.cookies?.[COOKIE] ?? "horror");
  res.locals.activeTheme  = key;
  res.locals.themeName    = def.name;
  res.locals.themeFont    = def.font;
  res.locals.themeCssVars = toCssVars(def);
  res.locals.allThemes    = allThemes();
  next();
}
