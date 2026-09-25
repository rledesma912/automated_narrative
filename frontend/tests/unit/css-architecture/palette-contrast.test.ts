import fs from "fs";
import path from "path";
import { describe, it, expect } from "vitest";

/**
 * Spec-531: la paleta «Papel» (`src/styles/theme.css`, `:root`) cumple contraste
 * WCAG AA (≥ 4,5:1) en cada par texto/fondo que usa la UI.
 */
const THEME = fs.readFileSync(path.resolve(__dirname, "../../../src/styles/theme.css"), "utf-8");

function vars(): Record<string, string> {
  const root = THEME.match(/:root\s*\{([\s\S]*?)\}/)?.[1] ?? "";
  return Object.fromEntries(
    [...root.matchAll(/--forge-([\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;/g)].map((m) => [m[1], m[2]]),
  );
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const TEXTS = ["text", "muted", "accent", "error", "warning", "success", "info"];
const BACKGROUNDS = ["bg", "surface"];
const PAIRS: Array<[string, string]> = [
  ...TEXTS.flatMap((t) => BACKGROUNDS.map((b): [string, string] => [t, b])),
  ["on-accent", "accent"],
  ["error", "error-bg"],
  ["warning", "warning-bg"],
  ["success", "success-bg"],
  ["info", "info-bg"],
];

describe("Spec-531 — contraste de la paleta", () => {
  const palette = vars();

  it("define todas las variables de color como hexadecimales", () => {
    const needed = new Set(PAIRS.flat());
    expect([...needed].filter((name) => !palette[name])).toEqual([]);
  });

  it.each(PAIRS)("--forge-%s sobre --forge-%s ≥ 4,5:1", (fg, bg) => {
    expect(contrast(palette[fg], palette[bg])).toBeGreaterThanOrEqual(4.5);
  });
});
