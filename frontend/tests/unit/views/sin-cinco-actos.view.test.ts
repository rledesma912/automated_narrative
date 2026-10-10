import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

/**
 * Spec-650: la cantidad de actos sale del largo de la historia (5 o 3), nunca de un 5
 * fijo en las vistas, el JS del navegador o el server del front. Los nombres de los
 * actos viven solo en `src/utils/actos.ts` (y su test los compara con el Core).
 */
const ROOT = path.resolve(__dirname, "../../..");

function files(dir: string, ext: string[]): string[] {
  return fs.readdirSync(path.join(ROOT, dir), { withFileTypes: true }).flatMap((e) => {
    const rel = `${dir}/${e.name}`;
    if (e.isDirectory()) return files(rel, ext);
    return ext.some((x) => e.name.endsWith(x)) ? [rel] : [];
  });
}

const FIJOS: RegExp[] = [
  /\|\|\s*5\b/, // «total || 5»
  /\b(?:number|p\.id|beat|acto|n)\s*[<>]=?\s*5\b/, // «a.number < 5», «n <= 5»
  /TOTAL_BEATS\s*=\s*5\b/,
  /\bcinco actos\b/i,
  /\b5 actos\b/i,
];
const NOMBRES = /Se complica|El peor momento|Qué hace después/;
// Línea → motivo.
const PERMITIDOS: Record<string, string> = {
  "public/js/eta.js:const LEGACY_TOTAL_BEATS = 5;": "jobs de antes de la Spec-650, sin total_beats: todos eran largos",
};

describe("Spec-650: sin 5 actos fijos en el front", () => {
  const all = [...files("src", [".ejs", ".ts"]), ...files("public/js", [".js"])];

  it("ningún archivo cuenta los actos con un 5", () => {
    const found: string[] = [];
    for (const f of all) {
      fs.readFileSync(path.join(ROOT, f), "utf8")
        .split("\n")
        .forEach((line, i) => {
          if (FIJOS.some((re) => re.test(line)) && !PERMITIDOS[`${f}:${line.trim()}`]) {
            found.push(`${f}:${i + 1}: ${line.trim()}`);
          }
        });
    }
    expect(found).toEqual([]);
  });

  it("los nombres de los actos están solo en utils/actos.ts", () => {
    const found = all.filter(
      (f) => f !== "src/utils/actos.ts" && NOMBRES.test(fs.readFileSync(path.join(ROOT, f), "utf8")),
    );
    expect(found).toEqual([]);
  });
});
