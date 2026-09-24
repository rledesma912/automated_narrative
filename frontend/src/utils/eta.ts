/**
 * «≈ N min» para mostrar antes de lanzar un job (Spec-510).
 * Mismo algoritmo que `formatEstimate` de public/js/eta.js (test de paridad).
 */
export function formatEstimate(seconds: unknown): string {
  if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds <= 0) return "";
  return `≈ ${Math.max(1, Math.round(seconds / 60))} min`;
}
