import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

/**
 * Bug (2026-09-27): un radio/checkbox `sr-only` es `position: absolute`. Si su
 * <label> no es `relative`, al recibir el foco (Tab) el navegador desplaza el <body>
 * —que tiene overflow-hidden— para mostrarlo, y la página queda en blanco. Todo
 * input `sr-only` de las tarjetas tiene que estar dentro de un label `relative`
 * (o `.opcion-forge`, que lo es por CSS: Spec-550 H9).
 */
const DIR = path.join(process.cwd(), "src/views/asistente");

// Spec-630 S2: las tarjetas de Preguntas y Los actos viven en partials.
describe.each(["direccion.ejs", "_taller_contenido.ejs", "_acto.ejs"])("%s", (file) => {
  it("cada input sr-only está dentro de un <label> relative", () => {
    const lines = fs.readFileSync(path.join(DIR, file), "utf-8").split("\n");
    const inputs = lines.flatMap((l, i) => (l.includes("<input") && l.includes('class="peer sr-only"') ? [i] : []));
    expect(inputs.length).toBeGreaterThan(0);
    const sinRelative = inputs.filter((i) => !/<label class="[^"]*\b(relative|opcion-forge)\b/.test(lines[i - 1]));
    expect(sinRelative.map((i) => i + 1)).toEqual([]);
  });
});
