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
  it("cada lugar tiene su tacho al lado, fuera de la opción, con los actos que lo usan (B7)", async () => {
    const html = await acto(1);
    for (const e of state.scenarios) {
      const grupo = html.match(new RegExp(`<span[^>]*data-lugar="${e.name}"[^>]*>([\\s\\S]*?)</span>\\s*</span>`))![1];
      expect(grupo).toMatch(/<\/label>\s*<button[^>]*data-borrar-lugar=/);
      expect(grupo).toContain(`data-usos="${e.acts.join(",")}"`);
    }
  });

  it("cada personaje tiene su tacho, menos quien narra (B7)", async () => {
    const html = await acto(1);
    expect(html).toContain('data-borrar-personaje="Tío Rubén"');
    expect(html).toContain('data-borrar-personaje="Los peones"');
    expect(html).not.toContain('data-borrar-personaje="Susana"');
    expect(html).toMatch(/data-borrar-personaje="Tío Rubén" data-usos="1,2,3,4,5"/);
  });

  it("borrar es un tacho «de la historia», y la pista dice cómo sacar a alguien de un acto (Spec-660 B2)", async () => {
    const html = await acto(1);
    const botones = html.match(/<button[^>]*data-borrar-(?:personaje|lugar)=[^>]*>[\s\S]*?<\/button>/g)!;
    expect(botones.length).toBeGreaterThan(0);
    for (const b of botones) {
      expect(b).toContain('data-lucide="trash-2"');
      expect(b).toContain('title="Borrar de la historia"');
      expect(b).toMatch(/aria-label="Borrar [^"]* de la historia"/);
    }
    expect(html).toContain("Destildá a alguien para sacarlo de este acto.");
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

  // Spec-630 B9: «Qué cambia» con el nombre, pista y rótulos visibles.
  it("«Cómo cambia Susana en este acto» con «Al empezar» y «Al terminar»", async () => {
    const html = await acto(2);
    expect(html).toContain("Cómo cambia Susana en este acto");
    expect(html).toMatch(/<label[^>]*for="change-from-2">Al empezar<\/label>\s*<textarea id="change-from-2" name="change_from"/);
    expect(html).toMatch(/<label[^>]*for="change-to-2">Al terminar<\/label>\s*<textarea id="change-to-2" name="change_to"/);
    expect(html).not.toContain("Qué cambia");
  });

  // Spec-630 B8: el secreto y «Se descubre en» van juntos en una caja.
  it("el secreto y «Se descubre en» van en la misma caja", async () => {
    const caja = (await acto(1)).match(/<div[^>]*data-secreto>([\s\S]*?)<\/textarea>/)![1];
    expect(caja).toContain("Lo que todavía es secreto");
    expect(caja).toMatch(/Se descubre en[\s\S]*?<option value="4" selected>el Acto 4<\/option>/);
    // El último acto no tiene en qué acto descubrirse.
    expect(await acto(5)).not.toContain('name="reveal_act"');
  });

  // Spec-630 B3/B4: columna derecha más ancha y separada.
  it("la columna derecha es más ancha y tiene la línea divisoria", async () => {
    const html = await acto(1);
    expect(html).toContain("lg:grid-cols-[1fr_24rem]");
    expect(html).toMatch(/<aside class="[^"]*lg:border-l[^"]*lg:pl-10/);
  });
});
