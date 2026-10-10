import { describe, it, expect } from "vitest";
import path from "path";

/** Spec-660 T1.1: el diálogo de confirmación con ícono y nota. */
// eslint-disable-next-line @typescript-eslint/no-require-imports
const confirmar = require(path.join(process.cwd(), "public/js/confirm-dialog.js"));

type Parte = { textContent: string; hidden: boolean; dataset: Record<string, string> };

/** Un diálogo de mentira con las mismas marcas que partials/confirm_dialog.ejs. */
function dialogo() {
  const parte = (dataset: Record<string, string> = {}): Parte => ({ textContent: "", hidden: false, dataset });
  const iconos = ["aviso", "escribir", "borrar"].map((i) => parte({ confirmIcono: i }));
  iconos[1].hidden = iconos[2].hidden = true;
  const partes: Record<string, Parte> = {
    "[data-confirm-titulo]": parte(),
    "[data-confirm-mensaje]": parte(),
    "[data-confirm-aceptar]": parte(),
    "[data-confirm-nota]": { ...parte(), hidden: true },
    "[data-confirm-nota-texto]": parte(),
  };
  return {
    partes,
    iconos,
    visible: () => iconos.filter((i) => !i.hidden).map((i) => i.dataset.confirmIcono),
    querySelector: (s: string) => partes[s],
    querySelectorAll: () => iconos,
  };
}

describe("ForgeConfirm.paint", () => {
  it("sin ícono ni nota queda como siempre: el aviso y sin nota", () => {
    const d = dialogo();
    confirmar.paint(d, { title: "¿Borrar?", message: "Se borra.", confirmLabel: "Borrar" });
    expect(d.visible()).toEqual(["aviso"]);
    expect(d.partes["[data-confirm-nota]"].hidden).toBe(true);
    expect(d.partes["[data-confirm-titulo]"].textContent).toBe("¿Borrar?");
    expect(d.partes["[data-confirm-aceptar]"].textContent).toBe("Borrar");
  });

  it("muestra solo el ícono pedido; uno desconocido vuelve al aviso", () => {
    const d = dialogo();
    confirmar.paint(d, { icon: "escribir" });
    expect(d.visible()).toEqual(["escribir"]);
    confirmar.paint(d, { icon: "borrar" });
    expect(d.visible()).toEqual(["borrar"]);
    confirmar.paint(d, { icon: "otro" });
    expect(d.visible()).toEqual(["aviso"]);
  });

  it("la nota aparece solo si viene, y se limpia en la siguiente", () => {
    const d = dialogo();
    confirmar.paint(d, { note: "Se escribe una versión nueva." });
    expect(d.partes["[data-confirm-nota]"].hidden).toBe(false);
    expect(d.partes["[data-confirm-nota-texto]"].textContent).toBe("Se escribe una versión nueva.");
    confirmar.paint(d, {});
    expect(d.partes["[data-confirm-nota]"].hidden).toBe(true);
    expect(d.partes["[data-confirm-nota-texto]"].textContent).toBe("");
  });

  it("los valores por defecto de siempre", () => {
    const d = dialogo();
    confirmar.paint(d);
    expect(d.partes["[data-confirm-titulo]"].textContent).toBe("¿Seguro?");
    expect(d.partes["[data-confirm-aceptar]"].textContent).toBe("Confirmar");
  });
});
