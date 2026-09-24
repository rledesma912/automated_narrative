import { createRequire } from "module";
import path from "path";
import { describe, it, expect } from "vitest";

/** Spec-510 T1.1: public/js/eta.js (script clásico UMD, se carga con require). */
const require = createRequire(import.meta.url);
const eta = require(path.join(process.cwd(), "public/js/eta.js"));

describe("progress", () => {
  it.each([
    [{ stage: "consolidando" }, 1],
    [{}, 0.03],
    [{ stage: "voz" }, 0.03],
    [{ stage: "desconocida", beat: 2 }, 0.03],
    [{ stage: "mapper", beat: 1, total_beats: 5 }, 0.02],
    [{ stage: "voz", beat: 3, total_beats: 5 }, 0.48],
    [{ stage: "journal", beat: 5, total_beats: 5 }, 0.97],
    [{ stage: "voz", beat: 2 }, 0.28], // total_beats por defecto: 5
    [{ stage: "journal", beat: 1, total_beats: 1 }, 0.85],
  ])("%o → %s", (job, expected) => {
    expect(eta.progress(job)).toBeCloseTo(expected, 5);
  });

  it("topea en 0,99 hasta consolidar", () => {
    expect(eta.progress({ stage: "journal", beat: 2, total_beats: 1 })).toBe(0.99);
  });

  it("da el mismo porcentaje que el banner de Spec-460", () => {
    const legacy = (job: { stage?: string; beat?: number; total_beats?: number }) => {
      if (job.stage === "consolidando") return 100;
      const stage = eta.STAGES[job.stage as string];
      if (!stage || !job.beat) return 3;
      const total = job.total_beats || 5;
      return Math.min(99, Math.round(((job.beat - 1 + stage.weight) / total) * 100));
    };
    for (const stage of Object.keys(eta.STAGES)) {
      for (let beat = 0; beat <= 5; beat++) {
        const job = { stage, beat, total_beats: 5 };
        expect(Math.round(eta.progress(job) * 100)).toBe(legacy(job));
      }
    }
  });
});

describe("remainingSeconds", () => {
  it.each([
    ["sin estimación", null, 10, 0.5, null],
    ["estimación 0", 0, 10, 0.5, null],
    ["transcurrido no numérico", 240, NaN, 0.5, null],
    ["al arrancar", 240, 0, 0, 240],
    ["poco avance: solo la estimación", 240, 30, 0.1, 210],
    ["ritmo igual a la estimación", 200, 100, 0.5, 100],
    ["ritmo más lento que lo estimado", 200, 150, 0.5, 100], // (0,5·50 + 0,5·150)
    ["ritmo más rápido", 200, 50, 0.5, 100], // (0,5·150 + 0,5·50)
    ["casi al final y lento", 200, 300, 0.95, 10], // (0,05·−100 + 0,95·15,79)
    ["terminado", 200, 250, 1, 0],
    ["pasado de la estimación sin avance", 200, 260, 0.05, -60],
    ["p fuera de rango se acota", 200, 100, 7, 0],
    ["transcurrido negativo cuenta como 0", 200, -5, 0, 200],
  ])("%s", (_name, estimated, elapsed, p, expected) => {
    const result = eta.remainingSeconds(estimated, elapsed, p);
    if (expected === null) expect(result).toBeNull();
    else expect(result).toBeCloseTo(expected as number, 2);
  });
});

describe("remainingFor", () => {
  it("usa params.estimated_seconds y el avance del relato completo", () => {
    const job = {
      kind: "full_generation",
      stage: "voz",
      beat: 3,
      total_beats: 5,
      params: { estimated_seconds: 200 },
    };
    // p = 0,48 → (0,52·100) + (0,48·(100/0,48 − 100)) = 52 + 52
    expect(eta.remainingFor(job, 100)).toBeCloseTo(104, 5);
  });

  it("regenerar un acto usa solo la estimación", () => {
    const job = { kind: "regenerate_voz", stage: "voz", beat: 5, params: { estimated_seconds: 60 } };
    expect(eta.remainingFor(job, 20)).toBe(40);
  });

  it("sin estimación en el job → null", () => {
    expect(eta.remainingFor({ kind: "full_generation", params: {} }, 20)).toBeNull();
    expect(eta.remainingFor({ kind: "full_generation" }, 20)).toBeNull();
  });
});

describe("formatRemaining", () => {
  it.each([
    [null, ""],
    [NaN, ""],
    [-3, "tardando más de lo habitual"],
    [0, "tardando más de lo habitual"],
    [1, "falta menos de 1 min"],
    [29, "falta menos de 1 min"],
    [30, "falta ≈ 1 min"],
    [89, "falta ≈ 1 min"],
    [90, "faltan ≈ 2 min"],
    [149, "faltan ≈ 2 min"],
    [150, "faltan ≈ 3 min"],
    [240, "faltan ≈ 4 min"],
  ])("%s → %s", (seconds, expected) => {
    expect(eta.formatRemaining(seconds)).toBe(expected);
  });
});

describe("formatDuration", () => {
  it.each([
    [null, ""],
    [-1, ""],
    [0, "0 s"],
    [42, "42 s"],
    [59.6, "1 min"],
    [60, "1 min"],
    [222, "3 min 42 s"],
    [720, "12 min"],
  ])("%s → %s", (seconds, expected) => {
    expect(eta.formatDuration(seconds)).toBe(expected);
  });
});

describe("formatEstimate", () => {
  it.each([
    [null, ""],
    [0, ""],
    [-60, ""],
    [10, "≈ 1 min"],
    [60, "≈ 1 min"],
    [89, "≈ 1 min"],
    [90, "≈ 2 min"],
    [240, "≈ 4 min"],
  ])("%s → %s", (seconds, expected) => {
    expect(eta.formatEstimate(seconds)).toBe(expected);
  });
});

describe("elapsedNow", () => {
  it("suma el tiempo local desde que llegó el evento", () => {
    expect(eta.elapsedNow({ elapsed_seconds: 100, received_at: 1_000 }, 16_000)).toBe(115);
  });

  it("un job que no arrancó cuenta desde que llegó", () => {
    expect(eta.elapsedNow({ elapsed_seconds: null, received_at: 1_000 }, 4_000)).toBe(3);
  });

  it("un reloj local que va para atrás no resta", () => {
    expect(eta.elapsedNow({ elapsed_seconds: 50, received_at: 9_000 }, 1_000)).toBe(50);
  });

  it("sin received_at → null", () => {
    expect(eta.elapsedNow({ elapsed_seconds: 50 }, 1_000)).toBeNull();
    expect(eta.elapsedNow(null, 1_000)).toBeNull();
  });
});
