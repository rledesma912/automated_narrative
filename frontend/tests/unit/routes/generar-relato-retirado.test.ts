import express from "express";
import request from "supertest";
import { describe, it } from "vitest";
import router from "../../../src/routes";

/** Spec-550 H4: «Generar Relato» (duplicaba la última variante sin IA) ya no existe. */
describe("POST /historia/:id/generar-relato", () => {
  it("responde 404", async () => {
    const app = express();
    app.use("/", router);
    await request(app).post("/historia/s-1/generar-relato").expect(404);
  });
});
