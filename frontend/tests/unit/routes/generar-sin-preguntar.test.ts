import express from "express";
import request from "supertest";
import { describe, it, expect, vi } from "vitest";

vi.mock("axios");
import axios from "axios";
import router from "../../../src/routes";

/** Spec-660 D2: el POST viejo no lanza nada (escribir se pregunta donde está el botón). */
describe("POST /historia/:id/generar", () => {
  const app = express();
  app.use("/", router);

  it("lleva a la sala sin crear un job", async () => {
    const res = await request(app).post("/historia/s-1/generar").expect(302);
    expect(res.headers.location).toBe("/generar/stream/s-1");
    expect(axios.post).not.toHaveBeenCalled();
  });

  it("con htmx, por HX-Redirect", async () => {
    const res = await request(app).post("/historia/s-1/generar").set("HX-Request", "true").expect(200);
    expect(res.headers["hx-redirect"]).toBe("/generar/stream/s-1");
    expect(axios.post).not.toHaveBeenCalled();
  });
});
