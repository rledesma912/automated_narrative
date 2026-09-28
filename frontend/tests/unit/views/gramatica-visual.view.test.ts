import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

/**
 * Spec-550 H9: botón, chip y nota se distinguen. Un chip o una nota informan: no
 * son <button> ni <a>, y no reaccionan al mouse. Los estados (éxito, aviso, error,
 * info) se pintan con las clases compartidas, no armados a mano en cada vista.
 */
const ROOT = path.resolve(__dirname, "../../..");
const DIRS = ["src/views", "public/js"];
const EXT = [".ejs", ".js"];

function files(dir: string): string[] {
  return fs.readdirSync(path.join(ROOT, dir), { withFileTypes: true }).flatMap((e) => {
    const rel = path.join(dir, e.name);
    if (e.isDirectory()) return files(rel);
    return EXT.includes(path.extname(e.name)) ? [rel] : [];
  });
}

const SOURCES = DIRS.flatMap(files).map((f) => [f, fs.readFileSync(path.join(ROOT, f), "utf-8")] as const);

/** Adorno que no es un estado: el ícono del modal de borrar. */
const EXCEPTIONS = ["src/views/partials/modal_confirm.ejs:p-3 bg-forge-error-bg rounded-full", "src/views/partials/layout.ejs:border-forge-error-border"];

describe("gramática visual", () => {
  it("chips y notas no son botones ni links, ni llevan hover", () => {
    const bad: string[] = [];
    for (const [file, text] of SOURCES) {
      for (const m of text.matchAll(/<(\w+)[^>]*class="([^"]*\b(?:chip-forge|nota-forge)\b[^"]*)"/g)) {
        const [, tag, cls] = m;
        if (["button", "a"].includes(tag) || /\bhover:/.test(cls)) bad.push(`${file}: <${tag} class="${cls}">`);
      }
    }
    expect(bad).toEqual([]);
  });

  it("sin estilos de estado armados a mano (bg-…-bg / border-…-border)", () => {
    const bad: string[] = [];
    for (const [file, text] of SOURCES) {
      for (const m of text.matchAll(/(?:bg-forge-(?:success|warning|error|info)-bg|border-forge-(?:success|warning|error|info)-border)/g)) {
        const line = text.slice(text.lastIndexOf("\n", m.index) + 1, text.indexOf("\n", m.index));
        if (!EXCEPTIONS.some((e) => e.startsWith(`${file}:`) && line.includes(e.split(":").slice(1).join(":")))) bad.push(`${file}: ${line.trim()}`);
      }
    }
    expect(bad).toEqual([]);
  });
});
