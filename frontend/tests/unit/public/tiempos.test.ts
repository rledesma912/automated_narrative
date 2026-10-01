import { createRequire } from "module";
import fs from "fs";
import path from "path";
import { describe, it, expect } from "vitest";

/**
 * Spec-610 T1.3: public/js/tiempos.js con los mismos casos que
 * src/application/services/video/timing.py (tests/fixtures/video/tiempos_casos.json).
 */
const require = createRequire(import.meta.url);
const tiempos = require(path.join(process.cwd(), "public/js/tiempos.js"));
const CASOS = JSON.parse(
  fs.readFileSync(path.join(process.cwd(), "../tests/fixtures/video/tiempos_casos.json"), "utf-8"),
);

describe("tiempos.js", () => {
  it.each(CASOS.palabras)("palabras %#", (c: { texto: string; palabras: number }) => {
    expect(tiempos.palabras(c.texto)).toBe(c.palabras);
  });
  it.each(CASOS.segundos)("segundos %#", (c: { palabras: number; ppm: number; segundos: number }) => {
    expect(tiempos.segundos(c.palabras, c.ppm)).toBe(c.segundos);
  });
  it.each(CASOS.reloj)("reloj %#", (c: { segundos: number; texto: string }) => {
    expect(tiempos.reloj(c.segundos)).toBe(c.texto);
  });
  it.each(CASOS.largo)("largo %#", (c: { segundos: number; texto: string }) => {
    expect(tiempos.largo(c.segundos)).toBe(c.texto);
  });
  it.each(CASOS.episodio)(
    "episodio %#",
    (c: { segundos: number; desde: number; hasta: number; estado: string }) => {
      expect(tiempos.episodio(c.segundos, c.desde, c.hasta)).toBe(c.estado);
    },
  );
});
