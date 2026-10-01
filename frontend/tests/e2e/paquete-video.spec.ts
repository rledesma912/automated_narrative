import { test, expect } from "@playwright/test";
import { storyIdByTitle } from "./support/stories";

/**
 * Spec-610 T2.6: «Armar el guion para el video» desde el panel del relato. Lanza el
 * job `video_script` con el modal que bloquea la página y, al terminar, abre
 * «Para el video». Arnés con LLM mock y DB descartable.
 */
let STORY_ID = "";
test.beforeAll(async ({ request }) => {
  STORY_ID = await storyIdByTitle(request, "El monte prohibido");
});

test.describe.configure({ mode: "serial" });
test.skip(!!process.env.BASE_URL, "Arma paquetes: solo contra el arnés con DB descartable");

test("cancelar la confirmación no lanza nada", async ({ page }) => {
  await page.goto(`/historia/${STORY_ID}/relatos`);
  const boton = page.locator("[data-relato-panel].active [data-armar-guion]");
  let jobs = 0;
  page.on("request", (r) => r.method() === "POST" && r.url().includes("/jobs") && jobs++);

  await boton.click();
  const dialogo = page.locator("#forge-confirm");
  await expect(dialogo).toContainText("¿Armar el guion para el video?");
  await dialogo.getByRole("button", { name: "Cancelar" }).click();
  await page.waitForTimeout(300);
  expect(jobs).toBe(0);
});

test("armar el guion abre el modal y termina en «Para el video»", async ({ page }) => {
  await page.goto(`/historia/${STORY_ID}/relatos`);
  const panel = page.locator("[data-relato-panel].active");
  const narrativeId = await panel.getAttribute("data-relato-panel");

  await panel.locator("[data-armar-guion]").click();
  await page.locator("#forge-confirm").getByRole("button", { name: "Armar el guion" }).click();

  await page.waitForURL(new RegExp(`/relatos/${narrativeId}/video$`), { timeout: 20_000 });
  await expect(page.locator("[data-bloque]").first()).toBeVisible();
  await expect(page.locator("[data-momento]").first()).toBeVisible();
  await expect(page.locator("[data-video]")).toContainText("Buenas noches");

  // De vuelta en los relatos, la variante ya tiene su paquete.
  await page.goto(`/historia/${STORY_ID}/relatos`);
  await expect(page.locator(`[data-para-el-video="${narrativeId}"]`)).toBeVisible();
});
