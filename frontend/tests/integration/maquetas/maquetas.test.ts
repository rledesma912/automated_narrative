import { afterEach, describe, expect, it, vi } from "vitest";
import request from "supertest";

/**
 * Spec-530 S0: las maquetas del asistente se sirven fuera de producción y no
 * existen en producción.
 */
async function loadApp(nodeEnv: string) {
  vi.resetModules();
  vi.stubEnv("NODE_ENV", nodeEnv);
  return (await import("../../../src/app")).default;
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("Maquetas del asistente (Spec-530 S0)", () => {
  it.each([
    ["direccion", "¿Qué historia querés contar?"],
    ["taller", "Preguntas abiertas"],
    ["escaleta", "Acto 5 · Desenlace"],
  ])("GET /maquetas/%s responde con la maqueta", async (pagina, texto) => {
    const app = await loadApp("development");
    const r = await request(app).get(`/maquetas/${pagina}`);
    expect(r.status).toBe(200);
    expect(r.text).toContain(texto);
    expect(r.text).toContain("Maqueta.");
  });

  it("/maquetas redirige a la primera", async () => {
    const app = await loadApp("development");
    const r = await request(app).get("/maquetas");
    expect(r.status).toBe(302);
    expect(r.headers.location).toBe("/maquetas/direccion");
  });

  it("una maqueta inexistente da 404", async () => {
    const app = await loadApp("development");
    expect((await request(app).get("/maquetas/otra")).status).toBe(404);
  });

  it("en producción no existen", async () => {
    const app = await loadApp("production");
    expect((await request(app).get("/maquetas/taller")).status).toBe(404);
  });
});
