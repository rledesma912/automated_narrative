/**
 * «dd/mm/yyyy hh:mm» en hora de Argentina (el contenedor corre en UTC). Es el
 * rótulo de cada versión del relato (Spec-630 B13, B21).
 */
export function fechaVersion(iso: string | undefined): string {
  return new Date(iso || Date.now())
    .toLocaleString("es-AR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: "America/Argentina/Buenos_Aires",
    })
    .replace(",", "");
}
