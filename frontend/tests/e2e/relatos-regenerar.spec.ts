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

test("regenerar un acto responde al instante y el panel se actualiza solo", async ({ page }) => {
  page.on("dialog", (d) => d.accept()); // hx-confirm
  await page.goto(`/historia/${STORY_ID}/relatos`);
  const panel = page.locator("[data-relato-panel].active");
  await panel.waitFor();
  const before = await panel.locator(`#relato-content-${await panel.getAttribute("data-relato-panel")}`).innerText();

  const started = Date.now();
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.url().includes("/actos/1/regenerar")),
    panel.locator('[data-regenerar-acto="1"]').click(),
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
});

test("mientras se regenera, el panel lo indica y bloquea los botones", async ({ page }) => {
  page.on("dialog", (d) => d.accept());
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

  const regenerating = page.locator("[data-relato-panel].active [data-refresh-on-job]");
  await expect(regenerating).toContainText(`Regenerando el acto ${target}`);
  await expect(
    page.locator(`[data-relato-panel].active [data-regenerar-acto="${other}"]`),
  ).toBeDisabled();
  await expect(regenerating).toHaveCount(0, { timeout: 10_000 });
});
