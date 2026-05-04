import express from "express";
import { describe, it, expect } from "vitest";
import request from "supertest";
import { createApiProxy } from "../../src/middleware/api_proxy";
import { startMockBackend } from "../helpers/mock_backend";

/**
 * Verifica que GET, POST, PATCH y DELETE viajan transparentes por el proxy:
 * método, path, headers y body llegan al backend sin alteración.
 */
describe("api proxy — HTTP method passthrough", () => {
  it.each([
    ["GET", "/api/v1/health", undefined],
    ["POST", "/api/v1/stories?action=save", { title: "T1" }],
    ["PATCH", "/api/v1/stories/abc/status", { status: "processing" }],
    ["DELETE", "/api/v1/stories/abc", undefined],
  ])("forwards %s requests transparently", async (method, path, body) => {
    let captured: { method?: string; url?: string; body?: string } = {};

    const backend = await startMockBackend((req, res) => {
      let data = "";
      req.on("data", (chunk) => (data += chunk));
      req.on("end", () => {
        captured = { method: req.method, url: req.url, body: data };
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true }));
      });
    });

    const app = express();
    app.use(createApiProxy(backend.url));

    let r;
    if (method === "GET") {
      r = await request(app).get(path);
    } else if (method === "POST") {
      r = await request(app).post(path).send(body);
    } else if (method === "PATCH") {
      r = await request(app).patch(path).send(body);
    } else {
      r = await request(app).delete(path);
    }

    expect(r.status).toBe(200);
    expect(captured.method).toBe(method);
    expect(captured.url).toBe(path);

    if (body !== undefined) {
      expect(JSON.parse(captured.body!)).toEqual(body);
    }

    await backend.close();
  });

  it("propagates non-2xx status codes from backend", async () => {
    const backend = await startMockBackend((_req, res) => {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ detail: "not found" }));
    });

    const app = express();
    app.use(createApiProxy(backend.url));

    const r = await request(app).get("/api/v1/missing");
    expect(r.status).toBe(404);
    expect(r.body).toEqual({ detail: "not found" });

    await backend.close();
  });
});
