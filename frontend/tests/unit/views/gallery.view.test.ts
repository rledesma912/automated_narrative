import { describe, it, expect } from "vitest";
import ejs from "ejs";
import path from "path";
import { rutas } from "../../../src/utils/rutas";

const viewPath = path.join(process.cwd(), "src/views/gallery.ejs");

describe("gallery view", () => {
  it("exposes a delete story CTA for completed stories", async () => {
    const html = await ejs.renderFile(viewPath, {
      rutas,
      stories: [
        {
          id: "story-1",
          title: "La casa",
          status: "completed",
          created_at: "2026-05-05T10:00:00.000Z",
          atmosfera: "terror",
        },
      ],
    });

    expect(html).toContain('hx-get="/modales/confirmar-borrar/story-1"');
    expect(html).toContain('hx-target="#modal-slot"');
    expect(html).toContain("Eliminar");
    expect(html).toContain('id="modal-slot"');
    expect(html).toContain("Ver relato");
  });

  it.each(["draft", "processing", "completed", "failed"])(
    "sin «Vista» ni links a la ficha, y el título no es link (%s)",
    async (status) => {
      const html = await ejs.renderFile(viewPath, {
        rutas,
        stories: [
          { id: "story-1", title: "La casa", status, created_at: "2026-05-05T10:00:00.000Z" },
        ],
      });

      // Spec-630 B12: la ficha se fue.
      expect(html).not.toContain("Vista");
      expect(html).not.toMatch(/href="\/historia\/story-1"/);
      expect(html).not.toMatch(/<a[^>]*>\s*<h3/);
    }
  );

  it.each(["draft", "processing", "completed", "failed"])(
    "no lanza generaciones desde la tarjeta (%s)",
    async (status) => {
      const html = await ejs.renderFile(viewPath, {
        rutas,
        stories: [
          { id: "story-1", title: "La casa", status, created_at: "2026-05-05T10:00:00.000Z" },
        ],
      });

      // Spec-630 B14: se escribe desde «Los actos» o desde «El relato», nunca a ciegas.
      expect(html).not.toContain("data-generation-trigger");
      expect(html).not.toContain('action="/historia/story-1/generar"');
      expect(html).not.toMatch(/Regenerar|Reintentar|Generar relato/);
    }
  );

  it.each(["draft", "completed", "failed"])("«Editar» abre «Los actos» (%s)", async (status) => {
    const html = await ejs.renderFile(viewPath, {
      rutas,
      stories: [{ id: "story-1", title: "La casa", status, created_at: "2026-05-05T10:00:00.000Z" }],
    });

    // Spec-630 B1.
    expect(html).toMatch(/<a href="\/asistente\/story-1\/escaleta"[^>]*>\s*<i[^>]*><\/i> Editar\s*<\/a>/);
    expect(html).not.toContain("/direccion");
  });
});

describe("fecha de la galería", () => {
  it("se muestra en hora de Argentina aunque el proceso corra en UTC", async () => {
    const tz = process.env.TZ;
    process.env.TZ = "UTC"; // como el contenedor
    try {
      const html = await ejs.renderFile(viewPath, {
        rutas,
        stories: [
          { id: "s1", title: "t", status: "draft", created_at: "2026-09-23T08:17:52.373051-03:00" },
        ],
      });
      expect(html).toContain("23/09/2026, 08:17");
      expect(html).not.toContain("11:17");
    } finally {
      process.env.TZ = tz;
    }
  });

  // Spec-630 B21: la galería dice también cuándo falta el guion.
  it("una historia terminada dice si tiene guion para el video", async () => {
    const html = await ejs.renderFile(viewPath, {
      rutas,
      stories: [
        { id: "con", title: "Con", status: "completed", created_at: "2026-10-01T10:00:00.000Z", video_narrative_id: "n-1" },
        { id: "sin", title: "Sin", status: "completed", created_at: "2026-10-01T10:00:00.000Z" },
        { id: "borrador", title: "Borrador", status: "draft", created_at: "2026-10-01T10:00:00.000Z" },
      ],
    });
    expect(html).toContain('href="/historia/con/relatos/n-1/video"');
    expect(html.match(/data-sin-guion/g)).toHaveLength(1);
    expect(html).toMatch(/href="\/historia\/sin\/relatos"[\s\S]*?data-sin-guion[\s\S]*?confirmar-borrar\/sin/);
  });
});
