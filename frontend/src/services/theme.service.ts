import path from "path";
import themes from "../../config/themes.json";

export type ThemeKey = keyof typeof themes;

export interface ThemeDef {
  name: string;
  bg: string;
  surface: string;
  border: string;
  accent: string;
  muted: string;
  text: string;
  font: "mono" | "serif" | "sans";
}

const THEMES = themes as Record<string, ThemeDef>;
const DEFAULT: ThemeKey = "horror";

export function getTheme(key: string): { key: string; def: ThemeDef } {
  const def = THEMES[key] ?? THEMES[DEFAULT];
  return { key: THEMES[key] ? key : DEFAULT, def };
}

export function allThemes(): Array<{ key: string; def: ThemeDef }> {
  return Object.entries(THEMES).map(([key, def]) => ({ key, def }));
}

/** Converts a ThemeDef into CSS custom property declarations. */
export function toCssVars(def: ThemeDef): string {
  return [
    `--forge-bg: ${def.bg}`,
    `--forge-surface: ${def.surface}`,
    `--forge-border: ${def.border}`,
    `--forge-accent: ${def.accent}`,
    `--forge-muted: ${def.muted}`,
    `--forge-text: ${def.text}`,
  ].join("; ");
}
