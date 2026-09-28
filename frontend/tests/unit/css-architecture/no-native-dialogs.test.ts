import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

/**
 * Spec-550 H8: nada de confirm()/alert()/prompt() del navegador en el frontend;
 * las confirmaciones usan ForgeConfirm (public/js/confirm-dialog.js).
 */
const ROOT = path.resolve(__dirname, "../../..");
const DIRS = ["src/views", "public/js", "src"];
const EXT = [".ejs", ".js", ".ts"];

function files(dir: string): string[] {
  return fs.readdirSync(path.join(ROOT, dir), { withFileTypes: true }).flatMap((e) => {
    const rel = path.join(dir, e.name);
    if (e.isDirectory()) return files(rel);
    return EXT.includes(path.extname(e.name)) ? [rel] : [];
  });
}

describe("sin diálogos nativos del navegador", () => {
  it("no hay confirm(), alert() ni prompt()", () => {
    const bad = [...new Set(DIRS.flatMap(files))].flatMap((f) => {
      const text = fs.readFileSync(path.join(ROOT, f), "utf-8");
      return [...text.matchAll(/(?<![\w.$-])(?:window\.)?(?:confirm|alert|prompt)\s*\(/g)].map((m) => `${f}: ${m[0]}`);
    });
    expect(bad).toEqual([]);
  });
});
