import express from "express";
import { describe, it, expect } from "vitest";
import request from "supertest";
import http from "http";
import { createApiProxy } from "../../../src/middleware/api_proxy";
import { startMockBackend } from "../../helpers/mock_backend";

describe("createApiProxy", () => {
  it("forwards GET /api/* requests preserving the prefix", async () => {
    const backend = await startMockBackend((req, res) => {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ path: req.url, method: req.method }));
    });

    const app = express();
    app.use(createApiProxy(backend.url));
    app.get("/internal/foo", (_req, res) => {
      res.json({ from: "express" });
    });

    const apiResp = await request(app).get("/api/v1/health");
    expect(apiResp.status).toBe(200);
    expect(apiResp.body.path).toBe("/api/v1/health");
    expect(apiResp.body.method).toBe("GET");

    // pathFilter solo intercepta /api/*; otras rutas siguen sirviéndose por Express
    const internalResp = await request(app).get("/internal/foo");
    expect(internalResp.status).toBe(200);
    expect(internalResp.body).toEqual({ from: "express" });

    await backend.close();
  });

  it("preserves response headers including content-type", async () => {
    const backend = await startMockBackend((_req, res) => {
      res.writeHead(200, {
        "Content-Type": "text/event-stream",
        "X-Custom-Header": "preserved",
      });
      res.end("data: ok\n\n");
    });

    const app = express();
    app.use(createApiProxy(backend.url));

    const resp = await request(app).get("/api/v1/test");
    expect(resp.status).toBe(200);
    expect(resp.headers["content-type"]).toBe("text/event-stream");
    expect(resp.headers["x-custom-header"]).toBe("preserved");

    await backend.close();
  });

  it("does not buffer chunked responses (first byte arrives before backend close)", async () => {
    const backend = await startMockBackend((_req, res) => {
      res.writeHead(200, { "Content-Type": "text/plain" });
      res.write("first");
      // Espera 200ms antes de cerrar. Si el proxy bufferea, el cliente recibe
      // todo de golpe a los 200ms; sin buffer, recibe "first" inmediatamente.
      setTimeout(() => {
        res.write("last");
        res.end();
      }, 200);
    });

    const app = express();
    app.use(createApiProxy(backend.url));
    const server = await new Promise<http.Server>((resolve) => {
      const s = app.listen(0, "127.0.0.1", () => resolve(s));
    });
    const port = (server.address() as { port: number }).port;

    const firstByteAt = await new Promise<number>((resolve, reject) => {
      const start = Date.now();
      const req = http.request(
        { hostname: "127.0.0.1", port, path: "/api/v1/test", method: "GET" },
        (res) => {
          res.once("data", () => resolve(Date.now() - start));
          res.on("error", reject);
        },
      );
      req.on("error", reject);
      req.end();
    });

    // Tolerancia generosa para CI lento; si bufferea, sería ≥ 200ms
    expect(firstByteAt).toBeLessThan(150);

    await new Promise<void>((r) => server.close(() => r()));
    await backend.close();
  });
});
