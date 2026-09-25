import path from "path";
import { test, type Page } from "@playwright/test";

import { storyIdByTitle } from "./support/stories";

/**
 * Spec-531 S0/S5: capturas de página completa de las pantallas principales, para
 * comparar el tema antes y después. No es un test de regresión: solo corre con
 * `CAPTURAS=<carpeta>` (p. ej. `CAPTURAS=antes npx playwright test visual-snapshots`)
 * y deja los PNG en `capturas/531/<carpeta>/` (fuera de `test-results/`, que Playwright
 * vacía en cada corrida; ignorada por git).
 */
const CARPETA = process.env.CAPTURAS || "";
const DESTINO = path.join(__dirname, "..", "..", "capturas", "531", CARPETA);

test.skip(!CARPETA, "Solo con CAPTURAS=<carpeta>");

async function capturar(page: Page, nombre: string, url: string) {
  await page.goto(url);
  // No "networkidle": el canal SSE global mantiene la red ocupada (Spec-460).
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(DESTINO, `${nombre}.png`), fullPage: true });
}

test.describe("Capturas del tema", () => {
  let storyId = "";

  test.beforeAll(async ({ request }) => {
    storyId = await storyIdByTitle(request, "El monte prohibido");
  });

  test("páginas", async ({ page }) => {
    await capturar(page, "01-home", "/");
    await capturar(page, "02-galeria", "/galeria");
    await capturar(page, "03-ficha", `/historia/${storyId}`);
    await capturar(page, "04-relatos", `/historia/${storyId}/relatos`);
    await capturar(page, "05-sala", `/generar/stream/${storyId}`);
    await capturar(page, "06-wizard-paso1", "/generar/paso/1");
    await capturar(page, "07-wizard-paso4", "/generar/paso/4");
    await capturar(page, "08-debug", "/debug");
  });

  // Spec-530 S0: las maquetas del asistente, enteras (el contenido scrollea dentro de
  // <main>, así que se agranda el viewport en vez de usar fullPage).
  test("maquetas del asistente", async ({ page }) => {
    for (const [nombre, alto] of [["direccion", 2600], ["taller", 2200], ["escaleta", 4200]] as const) {
      await page.setViewportSize({ width: 1440, height: alto });
      await capturar(page, `maqueta-${nombre}`, `/maquetas/${nombre}`);
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    await capturar(page, "maqueta-analizando", "/maquetas/taller");
    await page.getByRole("button", { name: /Armar la escaleta/ }).click();
    await page.screenshot({ path: path.join(DESTINO, "maqueta-analizando.png") });
  });

  test("modal de confirmación", async ({ page }) => {
    await page.goto("/galeria");
    await page.getByRole("button", { name: "Eliminar" }).first().click();
    await page.locator("#modal-slot > *").first().waitFor();
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(DESTINO, "09-modal.png") });
  });
});
