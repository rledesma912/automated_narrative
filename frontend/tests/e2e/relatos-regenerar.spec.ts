import { test, expect } from "@playwright/test";
import { storyIdByTitle } from "./support/stories";

/**
 * Regenerar un acto como job (Spec-460 S7): el request vuelve al instante y el
 * panel se actualiza solo cuando termina. Arnés con LLM mock (texto fijo).
 */
let STORY_ID = ""; // "El monte prohibido" de la semilla
test.beforeAll(async ({ request }) => {
  STORY_ID = await storyIdByTitle(request, "El monte prohibido");
});

test.describe.configure({ mode: "serial" });
test.skip(!!process.env.BASE_URL, "Modifica relatos: solo contra el arnés con DB descartable");

test("cancelar (o Esc) en la confirmación no regenera nada", async ({ page }) => {
  await page.goto(`/historia/${STORY_ID}/relatos`);
  const panel = page.locator("[data-relato-panel].active");
  await panel.waitFor();
  let pedidos = 0;
  page.on("request", (r) => r.url().includes("/regenerar") && pedidos++);
  const dialogo = page.locator("#forge-confirm");

  await panel.locator('[data-regenerar-acto="1"]').click();
  await expect(dialogo).toBeVisible();
  await expect(dialogo.getByRole("button", { name: "Cancelar" })).toBeFocused();
  await dialogo.getByRole("button", { name: "Cancelar" }).click();
  await expect(dialogo).toBeHidden();
  await expect(panel.locator('[data-regenerar-acto="1"]')).toBeFocused(); // el foco vuelve

  await panel.locator('[data-regenerar-acto="1"]').click();
  await expect(dialogo).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialogo).toBeHidden();
  await page.waitForTimeout(300);
  expect(pedidos).toBe(0);
});

test("regenerar un acto responde al instante y el panel se actualiza solo", async ({ page }) => {
  await page.goto(`/historia/${STORY_ID}/relatos`);
  const panel = page.locator("[data-relato-panel].active");
  await panel.waitFor();
  const before = await panel.locator(`#relato-content-${await panel.getAttribute("data-relato-panel")}`).innerText();

  // Spec-550 H8: la confirmación es el diálogo del tema, no el del navegador.
  await panel.locator('[data-regenerar-acto="1"]').click();
  const dialogo = page.locator("#forge-confirm");
  await expect(dialogo).toBeVisible();
  await expect(dialogo).toContainText("¿Regenerar el acto 1?");
  const started = Date.now();
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.url().includes("/actos/1/regenerar")),
    dialogo.getByRole("button", { name: "Regenerar el acto" }).click(),
  ]);
  const elapsed = Date.now() - started;

  expect(response.status()).toBe(200);
  expect(elapsed).toBeLessThan(500); // D2: ya no espera al LLM

  // Mientras corre: aviso y botones deshabilitados (o ya terminó, con el mock rápido).
  const status = page.locator("[data-relato-panel].active [data-refresh-on-job]");
  const after = page.locator("[data-relato-panel].active");
  await expect(status).toHaveCount(0, { timeout: 10_000 }); // se recargó solo
  await expect(after.locator("[data-panel-error]")).toHaveCount(0);
  await expect(after.locator('[data-regenerar-acto="1"]')).toBeEnabled();
  const now = await after.locator("[id^='relato-content-']").innerText();
  expect(now).not.toBe(before);
  // Spec-560 A2: los actos siguientes avisan que se escribieron con la versión anterior.
  await expect(after.locator("[data-acto-desactualizado]").first()).toBeVisible();
});

test("mientras se regenera, el panel lo indica y bloquea los botones", async ({ page }) => {
  await page.goto(`/historia/${STORY_ID}/relatos`);
  const panel = page.locator("[data-relato-panel].active");
  await panel.waitFor();

  // Retener la recarga del panel para ver el estado intermedio.
  await page.route("**/relatos/*/panel*", async (route) => {
    await new Promise((r) => setTimeout(r, 1_500));
    await route.continue();
  });
  // Usar los actos que tenga el relato del seed (no asumir numeración completa).
  const buttons = panel.locator("[data-regenerar-acto]");
  const target = await buttons.nth(1).getAttribute("data-regenerar-acto");
  const other = await buttons.nth(2).getAttribute("data-regenerar-acto");
  await buttons.nth(1).click();
  await page.locator("#forge-confirm [data-confirm-aceptar]").click();

  const regenerating = page.locator("[data-relato-panel].active [data-refresh-on-job]");
  await expect(regenerating).toContainText(`Regenerando el acto ${target}`);
  await expect(
    page.locator(`[data-relato-panel].active [data-regenerar-acto="${other}"]`),
  ).toBeDisabled();
  // Spec-630 B15: las acciones de arriba también se bloquean mientras se regenera, y vuelven.
  const corregir = page.locator("[data-acciones-version]:not(.hidden) [data-corregir-relato]");
  await expect(corregir).toHaveAttribute("aria-disabled", "true");
  await expect(regenerating).toHaveCount(0, { timeout: 10_000 });
  await expect(corregir).not.toHaveAttribute("aria-disabled", "true");
  await expect(corregir).toHaveAttribute("href", /\/corregir$/);
});
