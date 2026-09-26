/**
 * Avance y tiempo de un job de generación (Spec-510).
 *
 * Funciones puras compartidas por la banda de generación y la sala. Script
 * clásico con patrón UMD: en el browser queda en `window.ForgeEta`; en Node
 * (Vitest) se exporta con `module.exports`.
 *
 * El tiempo restante se redondea y nunca es negativo: si el job se pasa de lo
 * previsto se dice «tardando más de lo habitual».
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.ForgeEta = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // Peso de cada etapa dentro de un acto (Spec-460 S5).
  const STAGES = {
    planificador: { label: "Armando la escaleta", weight: 0 },
    verificador: { label: "Revisando la escaleta", weight: 0 },
    voz: { label: "Narrando", weight: 0.1 },
    journal: { label: "Actualizando la memoria", weight: 0.85 },
    consolidando: { label: "Consolidando el relato", weight: 1 },
  };

  // Por debajo de este avance, el ritmo real todavía no dice nada.
  const MIN_PROGRESS_FOR_PACE = 0.15;

  function isPositive(n) {
    return typeof n === "number" && Number.isFinite(n) && n > 0;
  }

  /** Avance del job entre 0 y 1 (mínimo 0,03 al arrancar, tope 0,99 hasta consolidar). */
  function progress(job) {
    if (job.stage === "consolidando") return 1;
    const stage = STAGES[job.stage];
    if (!stage || !job.beat) return 0.03;
    const total = job.total_beats || 5;
    return Math.min(0.99, (job.beat - 1 + stage.weight) / total);
  }

  /**
   * Segundos que faltan, o null sin estimación.
   * Con poco avance: estimado − transcurrido. Después, mezcla el restante de la
   * estimación con el del ritmo real, pesando más el ritmo a medida que avanza.
   */
  function remainingSeconds(estimated, elapsed, p) {
    if (!isPositive(estimated) || typeof elapsed !== "number" || !Number.isFinite(elapsed)) {
      return null;
    }
    const t = Math.max(0, elapsed);
    const byEstimate = estimated - t;
    const pp = typeof p === "number" && Number.isFinite(p) ? Math.min(1, Math.max(0, p)) : 0;
    if (pp < MIN_PROGRESS_FOR_PACE) return byEstimate;
    const byPace = t / pp - t;
    return (1 - pp) * byEstimate + pp * byPace;
  }

  /**
   * Segundos transcurridos ahora: `elapsed_seconds` del Core (0 si todavía no
   * arrancó) más lo que pasó en el reloj local desde `received_at`.
   */
  function elapsedNow(job, now) {
    if (!job || typeof job.received_at !== "number") return null;
    const base = typeof job.elapsed_seconds === "number" ? job.elapsed_seconds : 0;
    return base + Math.max(0, (now - job.received_at) / 1000);
  }

  /** Restante de un job a partir de lo que trae su payload. */
  function remainingFor(job, elapsed) {
    const estimated = job && job.params ? job.params.estimated_seconds : null;
    // Consolidar es instantáneo: no es «tardando más», es el final.
    if (job && job.stage === "consolidando" && isPositive(estimated)) return 1;
    const p = job && job.kind === "full_generation" ? progress(job) : 0;
    return remainingSeconds(estimated, elapsed, p);
  }

  /** «faltan ≈ 3 min» · «falta ≈ 1 min» · «falta menos de 1 min» · «tardando más de lo habitual». */
  function formatRemaining(seconds) {
    if (typeof seconds !== "number" || !Number.isFinite(seconds)) return "";
    if (seconds <= 0) return "tardando más de lo habitual";
    if (seconds < 30) return "falta menos de 1 min";
    if (seconds < 90) return "falta ≈ 1 min";
    return `faltan ≈ ${Math.round(seconds / 60)} min`;
  }

  /** «42 s» · «3 min 42 s» · «12 min». */
  function formatDuration(seconds) {
    if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds < 0) return "";
    const total = Math.round(seconds);
    if (total < 60) return `${total} s`;
    const min = Math.floor(total / 60);
    const sec = total % 60;
    return sec === 0 ? `${min} min` : `${min} min ${sec} s`;
  }

  /** «≈ 4 min» (mínimo 1 min), o "" sin estimación. */
  function formatEstimate(seconds) {
    if (!isPositive(seconds)) return "";
    return `≈ ${Math.max(1, Math.round(seconds / 60))} min`;
  }

  return {
    STAGES,
    progress,
    remainingSeconds,
    elapsedNow,
    remainingFor,
    formatRemaining,
    formatDuration,
    formatEstimate,
  };
});
