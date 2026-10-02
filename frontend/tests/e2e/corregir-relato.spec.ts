import { test, expect, Page } from "@playwright/test";
import { storyIdByTitle } from "./support/stories";

/**
 * Spec-610 T1.5: corregir el relato en la web, un acto a la vez, con guardado
 * automático. Arnés con DB descartable (la semilla trae «El monte prohibido» con relato).
 */
let STORY_ID = "";
test.beforeAll(async ({ request }) => {
  STORY_ID = await storyIdByTitle(request, "El monte prohibido");
});

test.describe.configure({ mode: "serial" });
test.skip(!!process.env.BASE_URL, "Modifica relatos: solo contra el arnés con DB descartable");

async function abrirCorregir(page: Page): Promise<string> {
  await page.goto(`/historia/${STORY_ID}/relatos`);
  const link = page.locator("[data-acciones-version]:not(.hidden) [data-corregir-relato]");
  await link.click();
  await page.waitForURL(/\/corregir/);
  await page.locator("[data-corregir]").waitFor();
  return (await page.locator("[data-corregir]").getAttribute("data-narrative-id")) as string;
}

async function esperarGuardado(page: Page) {
  const aviso = page.locator("[data-guardado]");
  await expect(aviso).toHaveAttribute("data-estado", "ok", { timeout: 5_000 });
  await expect(aviso).not.toHaveAttribute("data-pendiente", "1");
}

test("se entra desde el panel del relato y se ve un acto a la vez", async ({ page }) => {
  await abrirCorregir(page);
  await expect(page.locator('[data-acto-panel="1"]')).toBeVisible();
  await expect(page.locator('[data-acto-panel="2"]')).toBeHidden();
  await expect(page.locator("[data-duracion-total]")).toHaveText(/^≈ \d/);

  await page.locator('nav [data-acto-tab="2"]').click();
  await expect(page.locator('[data-acto-panel="2"]')).toBeVisible();
  await expect(page.locator('[data-acto-panel="1"]')).toBeHidden();
  await expect(page.locator('[data-anterior="2"]')).toContainText("Así terminó el acto anterior");
  await expect(page).toHaveURL(/acto=2/);
});

test("lo corregido se guarda solo y sigue ahí al volver", async ({ page }) => {
  await abrirCorregir(page);
  await page.locator('nav [data-acto-tab="2"]').click();
  const cuadro = page.locator('[data-acto-texto="2"]');
  const resumen = page.locator('[data-acto-resumen="2"]');
  const antes = await resumen.innerText();

  await cuadro.click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type("\n\nAgregué este párrafo para la prueba de corregir.");
  await expect(resumen).not.toHaveText(antes); // la cuenta se actualiza mientras se escribe
  await esperarGuardado(page);

  await page.reload();
  await expect(page.locator('[data-acto-texto="2"]')).toHaveValue(/Agregué este párrafo para la prueba de corregir\.$/);
});

test("un acto vacío no se guarda", async ({ page }) => {
  await abrirCorregir(page);
  const cuadro = page.locator('[data-acto-texto="1"]');
  const original = await cuadro.inputValue();
  let puts = 0;
  page.on("request", (r) => r.method() === "PUT" && r.url().includes("/acts/") && puts++);

  // Como una persona: seleccionar todo y borrar (fill("") no dispara `input` en un textarea).
  await cuadro.click();
  await page.keyboard.press("Control+A");
  await page.keyboard.press("Backspace");
  const aviso = page.locator("[data-guardado]");
  await expect(aviso).toHaveAttribute("data-estado", "error", { timeout: 5_000 });
  await expect(aviso).toContainText("vacío");
  expect(puts).toBe(0);

  await cuadro.fill(original);
  await esperarGuardado(page);
});

test("regenerar un acto desde acá vuelve al mismo acto con el texto nuevo", async ({ page }) => {
  await abrirCorregir(page);
  await page.locator('nav [data-acto-tab="3"]').click();
  const antes = await page.locator('[data-acto-texto="3"]').inputValue();

  await page.locator('[data-regenerar="3"]').click();
  const dialogo = page.locator("#forge-confirm");
  await expect(dialogo).toContainText("¿Regenerar el acto 3?");
  await dialogo.getByRole("button", { name: "Regenerar el acto" }).click();

  await page.waitForURL(/acto=3/, { timeout: 15_000 });
  await expect(page.locator('[data-acto-panel="3"]')).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('[data-acto-texto="3"]')).not.toHaveValue(antes, { timeout: 15_000 });
  // Lo corregido en el acto 2 (prueba anterior) no se perdió.
  await expect(page.locator('[data-acto-texto="2"]')).toHaveValue(/Agregué este párrafo para la prueba de corregir\./);
});
