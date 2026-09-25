import fs from "fs";
import path from "path";
import { describe, it, expect } from "vitest";

/**
 * Spec-531: la paleta vive solo en `src/styles/theme.css`. En vistas, estilos y
 * scripts del cliente no puede haber colores fijos: ni hexadecimales ni rgb(), ni
 * negro/blanco ni las paletas de Tailwind (`text-red-400`, `bg-green-500/10`…).
 * Todo va por las variables `--forge-*` (clases `forge-*` de Tailwind).
 */
const ROOT = path.resolve(__dirname, "../../..");
const DIRS = ["src/views", "src/styles", "public/js"];
const EXTENSIONS = [".ejs", ".css", ".js"];
const PALETTE_FILE = "src/styles/theme.css";

const TAILWIND_PALETTES =
  "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose";
const PATTERNS: Array<[string, RegExp]> = [
  ["hexadecimal", /#[0-9a-fA-F]{3,8}\b/g],
  // rgb()/rgba() con números; `rgba(var(--forge-…))` no es un color fijo.
  ["rgb()", /rgba?\(\s*\d[^)]*\)/g],
  [
    "clase de color de Tailwind",
    new RegExp(
      String.raw`\b(?:bg|text|border|from|to|via|ring|fill|stroke|divide|outline|shadow|placeholder|decoration)-(?:black|white|(?:${TAILWIND_PALETTES})-\d{2,3})(?:\/\d+)?\b`,
      "g",
    ),
  ],
];

/** Excepciones justificadas: `archivo` → fragmentos permitidos. */
const EXCEPTIONS: Record<string, string[]> = {};

function files(dir: string): string[] {
  const abs = path.join(ROOT, dir);
  if (!fs.existsSync(abs)) return [];
  return fs.readdirSync(abs, { withFileTypes: true }).flatMap((entry) => {
    const rel = path.join(dir, entry.name);
    if (entry.isDirectory()) return files(rel);
    return EXTENSIONS.includes(path.extname(entry.name)) ? [rel] : [];
  });
}

function findings(): string[] {
  const out: string[] = [];
  for (const file of DIRS.flatMap(files)) {
    if (file === PALETTE_FILE) continue;
    const allowed = EXCEPTIONS[file] ?? [];
    const lines = fs.readFileSync(path.join(ROOT, file), "utf-8").split("\n");
    lines.forEach((line, i) => {
      for (const [kind, re] of PATTERNS) {
        for (const match of line.matchAll(re)) {
          if (allowed.includes(match[0])) continue;
          out.push(`${file}:${i + 1} ${kind}: ${match[0]}`);
        }
      }
    });
  }
  return out;
}

describe("Spec-531 — sin colores fijos fuera de theme.css", () => {
  it("vistas, estilos y scripts usan solo las variables del tema", () => {
    expect(findings()).toEqual([]);
  });
});
