/**
 * Spec-630 B1: un solo lugar arma la URL para editar una historia. Editar
 * siempre abre «Los actos», entre por donde entre. Las vistas lo usan como
 * `rutas.editarHref(id)` (app.locals); `public/js` arma la misma URL a mano.
 */
export function editarHref(storyId: string): string {
  return `/asistente/${encodeURIComponent(storyId)}/escaleta`;
}

export const rutas = { editarHref };
