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

  it("votar necesita el id del navegador; la nota, recortada y nunca vacía", () => {
    expect(tablero.cuerpoOpinion("a.png", "me_gusta", "ignorado", "nav-12345678")).toEqual({
      archivo: "a.png", tipo: "me_gusta", navegador: "nav-12345678",
    });
    expect(tablero.cuerpoOpinion("a.png", "me_gusta", "", "")).toBeNull();
    expect(tablero.cuerpoOpinion("a.png", "nota", "  más oscura ", "nav-12345678")).toEqual({
      archivo: "a.png", tipo: "nota", texto: "más oscura", navegador: "nav-12345678",
    });
    expect(tablero.cuerpoOpinion("a.png", "nota", "   ", "x")).toBeNull();
    expect(tablero.cuerpoOpinion("a.png", "voto", "", "nav-12345678")).toBeNull();
    expect(tablero.cuerpoOpinion("", "me_gusta", "", "nav-12345678")).toBeNull();
  });

  it("lee el id del navegador de la cookie (y descarta uno raro)", () => {
    expect(tablero.navegador("a=1; forge_navegador=0f3c9a2e-1111-4222-8333-444455556666; b=2")).toBe(
      "0f3c9a2e-1111-4222-8333-444455556666",
    );
    expect(tablero.navegador("forge_navegador=<script>")).toBe("");
    expect(tablero.navegador("")).toBe("");
  });
});
