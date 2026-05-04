import express from "express";
import http from "http";
import { describe, it, expect } from "vitest";
import { createApiProxy } from "../../src/middleware/api_proxy";
import { startMockBackend } from "../helpers/mock_backend";

/**
 * SSE end-to-end: backend mock que emite 5 eventos espaciados; cliente HTTP
 * lee chunks y mide deltas. Si el proxy bufferea, los deltas serían ~0
 * y el último chunk llegaría con todo el payload junto. Sin buffer, los
 * deltas reflejan el espaciado del backend (100ms cada uno, ±tolerancia).
 */
describe("api proxy — SSE streaming integrity", () => {
  it("streams 5 SSE events through the proxy without buffering", async () => {
    const EVENT_GAP_MS = 100;
    const TOTAL_EVENTS = 5;

    const backend = await startMockBackend((_req, res) => {
      res.writeHead(200, {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      });
      let n = 0;
      const interval = setInterval(() => {
        n += 1;
        res.write(`event: tick\ndata: {"n":${n}}\n\n`);
        if (n >= TOTAL_EVENTS) {
          clearInterval(interval);
          res.end();
        }
      }, EVENT_GAP_MS);
    });

    const app = express();
    app.use(createApiProxy(backend.url));
    const server = await new Promise<http.Server>((resolve) => {
      const s = app.listen(0, "127.0.0.1", () => resolve(s));
    });
    const port = (server.address() as { port: number }).port;

    const arrivals: number[] = [];
    const start = Date.now();

    await new Promise<void>((resolve, reject) => {
      const req = http.request(
        { hostname: "127.0.0.1", port, path: "/api/v1/stream", method: "GET" },
        (res) => {
          res.on("data", (chunk: Buffer) => {
            // Cada "data:" es un evento; chunks pueden traer varios o uno
            const events = chunk.toString().match(/event: tick/g) ?? [];
            for (let i = 0; i < events.length; i++) {
              arrivals.push(Date.now() - start);
            }
          });
          res.on("end", () => resolve());
          res.on("error", reject);
        },
      );
      req.on("error", reject);
      req.end();
    });

    expect(arrivals).toHaveLength(TOTAL_EVENTS);

    // Calcular deltas entre eventos consecutivos
    const deltas: number[] = [];
    for (let i = 1; i < arrivals.length; i++) {
      deltas.push(arrivals[i]! - arrivals[i - 1]!);
    }

    // Sin buffer: cada delta ≈ EVENT_GAP_MS (con tolerancia para event loop).
    // Con buffer: todos los eventos llegarían juntos al final → deltas cerca de 0
    // excepto uno enorme. Verificamos que el delta máximo no se va al techo
    // (que sería el caso si bufferea esperando el end()).
    const maxDelta = Math.max(...deltas);
    expect(maxDelta).toBeLessThanOrEqual(EVENT_GAP_MS + 100); // 200ms ceiling

    // Y que la dispersión es razonable (no todos colapsados)
    const spread = arrivals[arrivals.length - 1]! - arrivals[0]!;
    const expectedSpread = EVENT_GAP_MS * (TOTAL_EVENTS - 1);
    expect(spread).toBeGreaterThanOrEqual(expectedSpread - 100);

    await new Promise<void>((r) => server.close(() => r()));
    await backend.close();
  });
});
