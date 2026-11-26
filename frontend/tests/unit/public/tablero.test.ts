import { describe, it, expect } from "vitest";
import path from "path";

/** Spec-795: las funciones puras de public/js/tablero.js. */
// eslint-disable-next-line @typescript-eslint/no-require-imports
const tablero = require(path.join(process.cwd(), "public/js/tablero.js"));

describe("tablero.js (Spec-795)", () => {
  it("el visor da la vuelta en las dos puntas", () => {
    expect(tablero.mover(2, 1, 3)).toBe(0);
    expect(tablero.mover(0, -1, 3)).toBe(2);
    expect(tablero.mover(1, 1, 3)).toBe(2);
    expect(tablero.mover(0, 1, 0)).toBe(0);
  });

  it("me gusta y no va van sin texto; la nota, recortada y nunca vacía", () => {
    expect(tablero.cuerpoOpinion("a.png", "me_gusta", "ignorado")).toEqual({ archivo: "a.png", tipo: "me_gusta" });
    expect(tablero.cuerpoOpinion("a.png", "nota", "  más oscura ")).toEqual({ archivo: "a.png", tipo: "nota", texto: "más oscura" });
    expect(tablero.cuerpoOpinion("a.png", "nota", "   ")).toBeNull();
    expect(tablero.cuerpoOpinion("a.png", "voto")).toBeNull();
    expect(tablero.cuerpoOpinion("", "me_gusta")).toBeNull();
  });
});
