import { createRequire } from "module";
import fs from "fs";
import path from "path";
import { describe, it, expect } from "vitest";

/**
 * Spec-610 T3.3: public/js/marcas.js. `reubicar` pasa los mismos casos que
 * src/application/services/video/state.py (tests/fixtures/video/marcas_casos.json).
 */
const require = createRequire(import.meta.url);
const marcas = require(path.join(process.cwd(), "public/js/marcas.js"));
const CASOS = JSON.parse(
  fs.readFileSync(path.join(process.cwd(), "../tests/fixtures/video/marcas_casos.json"), "utf-8"),
);

describe("reubicar (casos compartidos con el Core)", () => {
  it.each(CASOS.reubicar.map((c: { nombre: string }) => [c.nombre, c]))("%s", (_n, c: any) => {
    const r = marcas.reubicar(c.palabras, c.marcas);
    expect(r.quedan).toEqual(c.quedan);
    expect(r.perdidas).toEqual(c.perdidas);
  });
});

describe("tocar y arrastrar", () => {
  it("tocar una palabra marca solo esa, y tocarla de nuevo la saca", () => {
    const una = marcas.alternarPalabra([], 3);
    expect(una).toEqual([[3, 3]]);
    expect(marcas.alternarPalabra(una, 3)).toEqual([]);
  });

  it("dos palabras seguidas forman una frase; sacar la del medio la parte", () => {
    let m = marcas.alternarPalabra([], 2);
    m = marcas.alternarPalabra(m, 3);
    m = marcas.alternarPalabra(m, 4);
    expect(m).toEqual([[2, 4]]);
    expect(marcas.alternarPalabra(m, 3)).toEqual([[2, 2], [4, 4]]);
  });

  it("arrastrar marca la frase; arrastrar de nuevo sobre lo marcado la saca", () => {
    const m = marcas.alternarTramo([[0, 0]], 5, 2);
    expect(m).toEqual([[0, 0], [2, 5]]);
    expect(marcas.alternarTramo(m, 2, 5)).toEqual([[0, 0]]);
  });

  it("arrastrar sobre una frase a medias la completa", () => {
    expect(marcas.alternarTramo([[3, 3]], 2, 4)).toEqual([[2, 4]]);
  });

  it("la clave ignora mayúsculas y signos alrededor", () => {
    expect(marcas.clave("¿Quién?")).toBe("quién");
    expect(marcas.clave("—y")).toBe("y");
  });
});
