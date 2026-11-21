import { createRequire } from "module";
import path from "path";
import { describe, it, expect } from "vitest";

/** Spec-760 A1: public/js/tope.js (UMD; en Node solo las funciones puras). */
const require = createRequire(import.meta.url);
const tope = require(path.join(process.cwd(), "public/js/tope.js"));
const TEXTOS = { cuenta: "{n} de {tope} letras", sobra: "Sobran {sobra} letras: acortalo un poco para que se guarde." };

describe("largo", () => {
  it("cuenta letras como la API (un emoji es una)", () => {
    expect(tope.largo("acá")).toBe(3);
    expect(tope.largo("🎃🎃")).toBe(2);
    expect(tope.largo("")).toBe(0);
  });
});

describe("miles", () => {
  it.each([
    [800, "800"],
    [20000, "20.000"],
    [1000000, "1.000.000"],
  ])("%d → %s", (n, s) => expect(tope.miles(n)).toBe(s));
});

describe("estado", () => {
  it("el contador aparece desde el 80 %", () => {
    expect(tope.estado("x".repeat(15999), 20000).visible).toBe(false);
    expect(tope.estado("x".repeat(16000), 20000).visible).toBe(true);
  });

  it("justo en el tope no sobra nada", () => {
    expect(tope.estado("x".repeat(20000), 20000)).toMatchObject({ excedido: false, sobra: 0 });
  });

  it("pasado el tope dice cuánto sobra", () => {
    expect(tope.estado("x".repeat(21300), 20000)).toMatchObject({ excedido: true, sobra: 1300 });
  });

  it("sin tope no hay contador", () => {
    expect(tope.estado("x".repeat(50000), 0)).toMatchObject({ visible: false, excedido: false });
  });
});

describe("texto", () => {
  it("cuenta lo escrito", () => {
    expect(tope.texto(tope.estado("x".repeat(16200), 20000), TEXTOS)).toBe("16.200 de 20.000 letras");
  });

  it("pasado, dice cuánto sobra", () => {
    expect(tope.texto(tope.estado("x".repeat(21300), 20000), TEXTOS)).toBe(
      "Sobran 1.300 letras: acortalo un poco para que se guarde.",
    );
  });
});
