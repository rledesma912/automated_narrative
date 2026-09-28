import ejs from "ejs";
import path from "path";
import { describe, expect, it } from "vitest";

/**
 * Spec-550 H4/H5: la ficha muestra un solo botón de generación según el estado
 * (sin «Generar Relato», que duplicaba la última variante sin IA) y «Ver relato».
 */
const viewPath = path.join(process.cwd(), "src/views/historia.ejs");

const render = (status: string) =>
  ejs.renderFile(viewPath, {
    story: { id: "s-1", title: "La casa", status, created_at: "2026-09-27T10:00:00Z", personajes_full: [] },
  });

describe("ficha: botones según el estado", () => {
  it.each([
    ["draft", "Generar relato"],
    ["pending", "Generar relato"],
    ["failed", "Reintentar"],
    ["completed", "Regenerar"],
  ])("%s → «%s»", async (status, label) => {
    const html = await render(status);
    expect(html).toContain(label);
    expect(html).not.toContain("generar-relato");
    expect(html).not.toContain("Generar Relato");
    expect(html).not.toContain("Generar historia");
  });

  it("con relato: Regenerar y «Ver relato», nada de generar desde cero", async () => {
    const html = await render("completed");
    expect(html).toContain("Ver relato");
    expect(html).not.toContain("Ver Relatos");
    expect(html).not.toMatch(/Generar relato|Reintentar/);
  });

  it("sin relato: no ofrece Regenerar ni Ver relato", async () => {
    const html = await render("draft");
    expect(html).not.toMatch(/Regenerar|Ver relato/);
  });

  it("generando: solo el estado y «Ver progreso»", async () => {
    const html = await render("processing");
    expect(html).toContain("Ver progreso");
    expect(html).not.toMatch(/Generar relato|Regenerar|Reintentar/);
  });
});
