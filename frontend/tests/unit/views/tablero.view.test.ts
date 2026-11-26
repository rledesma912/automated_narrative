import { describe, it, expect } from "vitest";
import ejs from "ejs";
import path from "path";

/** Spec-795: las vistas del tablero. */
const vista = (v: string) => path.join(process.cwd(), `src/views/tablero/${v}.ejs`);
const archivo = (nombre: string, extra: Record<string, unknown> = {}) => ({
  archivo: nombre,
  leyenda: `Leyenda ${nombre}`,
  url: `/api/v1/tablero/entregas/e1/archivos/${nombre}`,
  tipo_medio: "imagen",
  me_gusta: 0,
  no_va: 0,
  opiniones: [],
  ...extra,
});

describe("tablero: la lista", () => {
  const render = (entregas: unknown[], proyectos: unknown[] = [], proyecto = "") =>
    ejs.renderFile(vista("index"), { entregas, proyectos, proyecto });

  it("vacío: lo dice", async () => {
    expect(await render([])).toContain("Todavía no hay nada en el tablero.");
  });

  it("cada entrega con su proyecto, fecha, miniaturas y cuántas opiniones", async () => {
    const html = await render(
      [
        {
          id: "2026-11-26-hoja", titulo: "La hoja", proyecto: "calabaza", proyecto_nombre: "La calabaza de la cripta",
          fecha: "2026-11-26", archivos: [archivo("a.png"), archivo("voz.mp3", { tipo_medio: "audio" })],
          total_archivos: 6, opiniones: 3,
        },
      ],
      [{ slug: "calabaza", nombre: "La calabaza de la cripta" }, { slug: "miniaturas", nombre: "Miniaturas" }],
      "calabaza"
    );
    expect(html).toContain('href="/tablero/2026-11-26-hoja"');
    expect(html).toContain("26/11/2026");
    expect(html).toContain('loading="lazy"');
    expect(html).toContain("audio-lines");
    expect(html).toContain("y 4 más");
    expect(html).toContain("3 opiniones");
    expect(html).toMatch(/proyecto=calabaza" class="opcion-forge[^"]*"><span class="opcion-forge__caja opcion-forge__caja--elegida/);
  });
});

describe("tablero: una entrega", () => {
  const entrega = {
    id: "e1", titulo: "La hoja", proyecto: "calabaza", proyecto_nombre: "La calabaza de la cripta", fecha: "2026-11-26",
    filas: [{ titulo: "Maestra", archivos: [archivo("a.png", {
      me_gusta: 2, no_va: 1, mi_voto: "me_gusta",
      opiniones: [
        { id: 1, tipo: "me_gusta", texto: "", created_at: "2026-11-26T10:00:00" },
        { id: 2, tipo: "me_gusta", texto: "", created_at: "2026-11-26T10:01:00" },
        { id: 3, tipo: "no_va", texto: "", created_at: "2026-11-26T10:02:00" },
        { id: 4, tipo: "nota", texto: "<b>más</b> oscura", created_at: "2026-11-26T10:03:00" },
      ],
    }), archivo("b.png")] }],
    sueltas: [archivo("voz.mp3", { tipo_medio: "audio" }), archivo("clip.mp4", { tipo_medio: "video" })],
  };
  const render = (queMirar = "<p>Mirá esto</p>") => ejs.renderFile(vista("entrega"), { entrega, queMirar });

  it("qué mirar, la fila lado a lado y los medios según el tipo", async () => {
    const html = await render();
    expect(html).toContain("data-que-mirar");
    expect(html).toContain("<p>Mirá esto</p>");
    expect(html).toContain("repeat(2, minmax(0, 1fr))");
    expect(html).toContain('data-visor-item data-src="/api/v1/tablero/entregas/e1/archivos/a.png"');
    expect(html).toMatch(/<audio controls[^>]*voz\.mp3/);
    expect(html).toMatch(/<video controls[^>]*clip\.mp4/);
    expect(html).toContain("<script src=\"/js/tablero.js");
  });

  it("cada botón con su contador; el voto propio va lleno y la nota escapada", async () => {
    const html = await render();
    expect(html).toMatch(/class="btn-forge-sm !px-3" data-opinar="me_gusta" aria-pressed="true"/);
    expect(html).toMatch(/class="btn-forge-outline-sm !px-3" data-opinar="no_va" aria-pressed="false"/);
    expect(html).toContain('<span data-cuenta="me_gusta">2</span>');
    expect(html).toContain('<span data-cuenta="no_va">1</span>');
    expect(html).toContain("Sacar tu «Me gusta»");
    expect(html).not.toContain("Sacar un me gusta");
    expect(html).toContain('data-sacar="4" aria-label="Sacar la nota"');
    expect(html).toContain("&lt;b&gt;más&lt;/b&gt; oscura");
    expect(html).toContain("26/11/2026 10:03");
  });

  it("sin «Qué mirar», sin la nota", async () => {
    expect(await render("")).not.toContain("data-que-mirar");
  });
});
