import { expect, test, type Page } from "@playwright/test";

/**
 * Spec-550 H3: el menú lateral mide 13rem, se colapsa a una tira de íconos, lo
 * recuerda al recargar y al navegar, y el pie de actividad arranca donde termina.
 */
const ancho = (page: Page) => page.locator("aside").evaluate((a) => Math.round(a.getBoundingClientRect().width));
const pie = (page: Page) => page.locator("#global-status-footer").evaluate((f) => Math.round(f.getBoundingClientRect().left));

test("el menú se colapsa, lo recuerda y el pie lo acompaña", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => localStorage.removeItem("forge:sidebar"));
  await page.reload();
  expect(await ancho(page)).toBe(13 * 16);
  await expect.poll(() => pie(page)).toBe(13 * 16);

  const boton = page.locator("[data-sidebar-toggle]");
  await expect(boton).toHaveAttribute("aria-expanded", "true");
  await boton.click();
  await expect.poll(() => ancho(page)).toBe(56);
  await expect.poll(() => pie(page)).toBe(56);
  await expect(boton).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator("aside").getByRole("link", { name: "Mis historias" })).toBeVisible();

  await page.reload();
  expect(await ancho(page)).toBe(56);
  await page.locator("aside").getByRole("link", { name: "Mis historias" }).click();
  await expect(page).toHaveURL(/\/galeria$/);
  expect(await ancho(page)).toBe(56);
  await expect(page.locator("[data-sidebar-toggle]")).toHaveAttribute("aria-expanded", "false");

  await page.locator("[data-sidebar-toggle]").click();
  await expect.poll(() => ancho(page)).toBe(13 * 16);
});
