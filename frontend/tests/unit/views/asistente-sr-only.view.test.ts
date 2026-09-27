import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

/**
 * Bug (2026-09-27): un radio/checkbox `sr-only` es `position: absolute`. Si su
 * <label> no es `relative`, al recibir el foco (Tab) el navegador desplaza el <body>
 * —que tiene overflow-hidden— para mostrarlo, y la página queda en blanco. Todo
 * input `sr-only` de las tarjetas tiene que estar dentro de un label `relative`.
 */
const DIR = path.join(process.cwd(), "src/views/asistente");

describe.each(["direccion.ejs", "taller.ejs", "escaleta.ejs"])("%s", (file) => {
  it("cada input sr-only está dentro de un <label> relative", () => {
    const lines = fs.readFileSync(path.join(DIR, file), "utf-8").split("\n");
    const inputs = lines.flatMap((l, i) => (l.includes("<input") && l.includes('class="peer sr-only"') ? [i] : []));
    expect(inputs.length).toBeGreaterThan(0);
    const sinRelative = inputs.filter((i) => !/<label class="[^"]*\brelative\b/.test(lines[i - 1]));
    expect(sinRelative.map((i) => i + 1)).toEqual([]);
  });
});
