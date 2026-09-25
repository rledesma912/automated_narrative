import path from "path";
import { expect, test, type Page } from "@playwright/test";

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

  // Spec-530: las vistas del asistente, enteras (el contenido scrollea dentro de
  // <main>, así que se agranda el viewport en vez de usar fullPage).
  test("asistente de autoría", async ({ page }) => {
    const created = await page.request.post("/api/v1/authoring/stories", {
      data: {
        title: "Capturas: la pena del colectivo",
        premise: "José, chofer de micros, ve por el espejo a una mujer que murió en su micro.",
        effect: "pavor",
        ending: "Le deja flores y el alma descansa en paz.",
        ending_intentional: true,
        telling: "caso",
        protagonist_name: "José",
        protagonist_role: "Chofer de micros de larga distancia",
      },
    });
    const sid = (await created.json()).story_id;
    for (const kind of ["consult", "plan_outline"]) {
      const job = (await (await page.request.post(`/api/v1/stories/${sid}/jobs`, { data: { kind } })).json()).job_id;
      await expect
        .poll(async () => (await (await page.request.get(`/api/v1/jobs/${job}`)).json()).status, { timeout: 20000 })
        .toBe("done");
    }
    await page.setViewportSize({ width: 1440, height: 2400 });
    await capturar(page, "asistente-nuevo", "/nuevo");
    for (const [paso, alto] of [["direccion", 2600], ["taller", 2200], ["escaleta", 5200]] as const) {
      await page.setViewportSize({ width: 1440, height: alto });
      await capturar(page, `asistente-${paso}`, `/asistente/${sid}/${paso}`);
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    await capturar(page, "asistente-analizando", `/asistente/${sid}/taller`);
    await page.getByRole("button", { name: /Analizar de nuevo/ }).click();
    await page.locator("#asistente-analizando").waitFor();
    await page.screenshot({ path: path.join(DESTINO, "asistente-analizando.png") });
  });

  test("modal de confirmación", async ({ page }) => {
    await page.goto("/galeria");
    await page.getByRole("button", { name: "Eliminar" }).first().click();
    await page.locator("#modal-slot > *").first().waitFor();
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(DESTINO, "09-modal.png") });
  });
});
