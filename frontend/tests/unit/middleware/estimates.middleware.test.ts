import express from "express";
import request from "supertest";
import { createRequire } from "module";
import path from "path";
import { describe, it, expect } from "vitest";
import { createLoadEstimates } from "../../../src/middleware/estimates.middleware";
import { formatEstimate } from "../../../src/utils/eta";
import type { JobEstimates } from "../../../src/services/core_api.service";

/** Spec-510 T3.1: loadEstimates y formatEstimate. */

const ESTIMATES: JobEstimates = {
  full_generation: { seconds: 222, source: "history", samples: 3 },
  regenerate_voz: { seconds: 55, source: "default", samples: 0 },
};

function appWith(fetchEstimates: () => Promise<JobEstimates>, timeoutMs = 1500) {
  const app = express();
  app.get("/", createLoadEstimates(fetchEstimates, timeoutMs), (_req, res) => {
    res.json({ estimateLabels: res.locals.estimateLabels });
  });
  return app;
}

describe("loadEstimates", () => {
  it("deja las etiquetas «≈ N min» en res.locals", async () => {
    const resp = await request(appWith(async () => ESTIMATES)).get("/");

    expect(resp.status).toBe(200);
    expect(resp.body.estimateLabels).toEqual({
      full_generation: "≈ 4 min",
      regenerate_voz: "≈ 1 min",
    });
  });

  it("si el Core falla, la página sigue sin estimación", async () => {
    const resp = await request(appWith(async () => Promise.reject(new Error("down")))).get("/");

    expect(resp.status).toBe(200);
    expect(resp.body.estimateLabels).toBeNull();
  });

  it("si el Core tarda más que el timeout, la página no espera", async () => {
    const slow = () => new Promise<JobEstimates>((resolve) => setTimeout(() => resolve(ESTIMATES), 500));
    const started = Date.now();
    const resp = await request(appWith(slow, 50)).get("/");

    expect(resp.status).toBe(200);
    expect(resp.body.estimateLabels).toBeNull();
    expect(Date.now() - started).toBeLessThan(450);
  });

  it("una respuesta sin segundos válidos no deja etiquetas", async () => {
    const bad = { full_generation: { seconds: 0 }, regenerate_voz: {} } as unknown as JobEstimates;
    const resp = await request(appWith(async () => bad)).get("/");

    expect(resp.body.estimateLabels).toBeNull();
  });
});

describe("formatEstimate (TS) da lo mismo que eta.js", () => {
  const require = createRequire(import.meta.url);
  const eta = require(path.join(process.cwd(), "public/js/eta.js"));

  it.each([null, undefined, "240", NaN, -1, 0, 1, 29, 30, 89, 90, 150, 222, 240, 3600])(
    "%s",
    (seconds) => {
      expect(formatEstimate(seconds)).toBe(eta.formatEstimate(seconds));
    },
  );
});
