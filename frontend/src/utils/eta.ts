/**
 * «≈ N min» para mostrar antes de lanzar un job (Spec-510).
 * Mismo algoritmo que `formatEstimate` de public/js/eta.js (test de paridad).
 */
export function formatEstimate(seconds: unknown): string {
  if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds <= 0) return "";
  return `≈ ${Math.max(1, Math.round(seconds / 60))} min`;
}

/**
 * Spec-530: estimación de los análisis del asistente, que duran segundos:
 * «≈ 20 s» (múltiplos de 5) debajo de 90 s; si no, como `formatEstimate`.
 */
export function formatShortEstimate(seconds: unknown): string {
  if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds <= 0) return "";
  if (seconds < 90) return `≈ ${Math.max(5, Math.round(seconds / 5) * 5)} s`;
  return formatEstimate(seconds);
}
