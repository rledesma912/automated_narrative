import { describe, it, expect } from "vitest";
import ejs from "ejs";
import fs from "fs";
import path from "path";

/** Spec-630 S3: lugares, personajes y avisos en la tarjeta de un acto. */
const view = path.join(process.cwd(), "src/views/asistente/_acto.ejs");
const state = JSON.parse(
  fs.readFileSync(path.join(process.cwd(), "tests/fixtures/asistente/estado.json"), "utf8"),
);
const acto = (n: number) =>
  ejs.renderFile(view, { state, a: state.outline.acts.find((a: { number: number }) => a.number === n) });

describe("tarjeta del acto", () => {
  it("cada lugar tiene su «×» al lado, fuera de la opción, con los actos que lo usan (B7)", async () => {
    const html = await acto(1);
    for (const e of state.scenarios) {
      const grupo = html.match(new RegExp(`<span[^>]*data-lugar="${e.name}"[^>]*>([\\s\\S]*?)</span>\\s*</span>`))![1];
      expect(grupo).toMatch(/<\/label>\s*<button[^>]*data-borrar-lugar=/);
      expect(grupo).toContain(`data-usos="${e.acts.join(",")}"`);
    }
  });

  it("cada personaje tiene su «×», menos quien narra (B7)", async () => {
    const html = await acto(1);
    expect(html).toContain('data-borrar-personaje="Tío Rubén"');
    expect(html).toContain('data-borrar-personaje="Los peones"');
    expect(html).not.toContain('data-borrar-personaje="Susana"');
    expect(html).toMatch(/data-borrar-personaje="Tío Rubén" data-usos="1,2,3,4,5"/);
  });

  it("«+ Lugar» abre un campo con «Agregar» que no es parte del acto (B6)", async () => {
    const html = await acto(1);
    expect(html).not.toContain("scenario_new");
    expect(html).toMatch(/data-lugar-form[\s\S]*?data-lugar-nombre[\s\S]*?data-lugar-agregar/);
    expect(html).not.toMatch(/<input[^>]*data-lugar-nombre[^>]*\bname=/);
  });

  it("«Sumarlo a los personajes» lleva el nombre y la clave del aviso (B2)", async () => {
    const html = await acto(1);
    expect(html).toMatch(/data-sumar-personaje="Tío Rubén" data-aviso="elenco:tio ruben"/);
  });
});
