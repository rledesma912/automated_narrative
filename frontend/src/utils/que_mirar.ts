/**
 * Spec-795 D4: «Qué mirar» de una entrega del tablero, sin motor de Markdown.
 * Escapa todo y después arma párrafos (separados por una línea en blanco), listas (líneas
 * que empiezan con «- ») y **negritas**. Nada más: lo escribe Claude y alcanza.
 */
const escapar = (s: string): string =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");

const enLinea = (s: string): string => escapar(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

export function queMirarHtml(texto: string | null | undefined): string {
  const bloques = (texto ?? "").replace(/\r\n/g, "\n").split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
  return bloques
    .map((b) => {
      const lineas = b.split("\n").map((l) => l.trim());
      if (lineas.every((l) => l.startsWith("- "))) {
        return `<ul>${lineas.map((l) => `<li>${enLinea(l.slice(2))}</li>`).join("")}</ul>`;
      }
      return `<p>${lineas.map(enLinea).join("<br>")}</p>`;
    })
    .join("");
}
