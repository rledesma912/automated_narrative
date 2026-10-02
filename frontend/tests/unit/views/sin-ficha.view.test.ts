import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

/**
 * Spec-630 B12: la ficha de la historia (`/historia/{id}` a secas) ya no existe.
 * Ninguna vista ni script la enlaza: los links van a «Los actos» o al relato.
 */
const ROOTS = ["src/views", "public/js"].map((d) => path.join(process.cwd(), d));
const FICHA = /\/historia\/(?:<%=[^%]*%>|\$\{[^}]*\})(?=["'`])/;

function files(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) return files(full);
    return /\.(ejs|js)$/.test(e.name) ? [full] : [];
  });
}

describe("sin links a la ficha", () => {
  it.each(ROOTS.flatMap(files).map((f) => [path.relative(process.cwd(), f), f]))("%s", (_rel, file) => {
    const lines = fs
      .readFileSync(file as string, "utf8")
      .split("\n")
      .map((l, i) => ({ l, n: i + 1 }))
      .filter(({ l }) => FICHA.test(l));
    expect(lines.map(({ n, l }) => `${n}: ${l.trim()}`)).toEqual([]);
  });

  it("detecta un link a la ficha", () => {
    expect(FICHA.test('<a href="/historia/<%= s.id %>">')).toBe(true);
    expect(FICHA.test("href=`/historia/${id}`")).toBe(true);
    expect(FICHA.test('<a href="/historia/<%= s.id %>/relatos">')).toBe(false);
  });
});
