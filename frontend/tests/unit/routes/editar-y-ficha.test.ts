import express from "express";
import request from "supertest";
import { describe, it, expect, vi, beforeEach } from "vitest";

/** Lo que responde el Core a «¿hay un job activo?»; `"caido"` = no responde. */
let activo: unknown = null;
vi.mock("../../../src/services/core_api.service", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../src/services/core_api.service")>()),
  getActiveJob: async () => {
    if (activo === "caido") throw new Error("ECONNREFUSED");
    return activo;
  },
}));

const { default: router } = await import("../../../src/routes");

function app() {
  const a = express();
  a.use("/", router);
  return a;
}

beforeEach(() => {
  activo = null;
});

/** Spec-630 B1: la ruta vieja de edición abre «Los actos». */
describe("GET /generar/cargar/:id", () => {
  it("redirige (301) a «Los actos»", async () => {
    const res = await request(app()).get("/generar/cargar/s-1").expect(301);
    expect(res.headers.location).toBe("/asistente/s-1/escaleta");
  });
});

/** Spec-630 B12: la ficha se fue; los links viejos siguen andando. */
describe("GET /historia/:id", () => {
  it("sin job activo, a «Los actos»", async () => {
    const res = await request(app()).get("/historia/s-1").expect(302);
    expect(res.headers.location).toBe("/asistente/s-1/escaleta");
  });

  it("con un relato escribiéndose, a la sala", async () => {
    activo = ({ job_id: "j", story_id: "s-1", kind: "full_generation", status: "running" });
    const res = await request(app()).get("/historia/s-1").expect(302);
    expect(res.headers.location).toBe("/generar/stream/s-1");
  });

  it("con otro job (un análisis), a «Los actos», que muestra su modal", async () => {
    activo = ({ job_id: "j", story_id: "s-1", kind: "verify_outline", status: "running" });
    const res = await request(app()).get("/historia/s-1").expect(302);
    expect(res.headers.location).toBe("/asistente/s-1/escaleta");
  });

  it("con el Core caído, igual a «Los actos»", async () => {
    activo = "caido";
    const res = await request(app()).get("/historia/s-1").expect(302);
    expect(res.headers.location).toBe("/asistente/s-1/escaleta");
  });
});
