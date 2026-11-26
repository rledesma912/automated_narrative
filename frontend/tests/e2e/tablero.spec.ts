import { test, expect } from "@playwright/test";

/**
 * Spec-795: el tablero. El arnés publica «Prueba del tablero» (2 imágenes en una fila) en la
 * carpeta descartable: verla desde el menú, abrir el visor, opinar, recargar y sacar.
 */
test.describe.configure({ mode: "serial" });
test.skip(!!process.env.BASE_URL, "Opina: solo contra el arnés con DB descartable");

const ID = "2026-11-26-calabaza-prueba-e2e";

test("«Tablero» en el menú lleva a la lista y a la entrega", async ({ page }) => {
  await page.goto("/");
  await page.locator('aside a[href="/tablero"]').click();
  await page.waitForURL(/\/tablero$/);
  await page.locator(`[data-tablero-entrega="${ID}"]`).click();
  await page.waitForURL(new RegExp(`/tablero/${ID}$`));
  await expect(page.locator("h2")).toHaveText("Prueba del tablero");
  await expect(page.locator("[data-que-mirar] strong")).toHaveText("una");
  await expect(page.locator("[data-archivo]")).toHaveCount(2);
});

test("el visor abre grande y pasa a la siguiente", async ({ page }) => {
  await page.goto(`/tablero/${ID}`);
  await page.locator('[data-archivo="a.png"] [data-visor-item]').click();
  const visor = page.locator("[data-visor]");
  await expect(visor).toBeVisible();
  await expect(visor.locator("[data-visor-leyenda]")).toHaveText("Opción A");
  await page.keyboard.press("ArrowRight");
  await expect(visor.locator("[data-visor-leyenda]")).toHaveText("Opción B");
  await page.keyboard.press("Escape");
  await expect(visor).toBeHidden();
});

test("opinar, recargar y sacar", async ({ page }) => {
  await page.goto(`/tablero/${ID}`);
  const a = page.locator('[data-archivo="a.png"]');
  await a.locator('[data-opinar="me_gusta"]').click();
  await expect(a.locator('[data-cuenta="me_gusta"]')).toHaveText("Me gusta · 1");
  await a.locator('[data-opinar="me_gusta"]').click();
  await expect(a.locator('[data-cuenta="me_gusta"]')).toHaveText("Me gusta · 2");
  await a.locator("[data-nota-abrir]").click();
  await a.locator("[data-nota-form] textarea").fill("Más oscura, por favor");
  await a.locator('[data-nota-form] button[type="submit"]').click();
  await expect(a.locator("[data-nota]")).toContainText("Más oscura, por favor");

  await page.reload();
  await expect(a.locator('[data-cuenta="me_gusta"]')).toHaveText("Me gusta · 2");
  await expect(a.locator("[data-nota]")).toContainText("Más oscura, por favor");

  await a.locator("[data-nota] [data-sacar]").click();
  await page.locator("[data-confirm-aceptar]").click();
  await expect(a.locator("[data-nota]")).toHaveCount(0);
  await a.locator('[data-cuenta="me_gusta"] + [data-sacar]').click();
  await page.locator("[data-confirm-aceptar]").click();
  await expect(a.locator('[data-cuenta="me_gusta"]')).toHaveText("Me gusta · 1");

  await page.goto("/tablero");
  await expect(page.locator(`[data-tablero-entrega="${ID}"]`)).toContainText("1 opinión");
});
