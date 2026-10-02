import { test, expect } from "@playwright/test";

/**
 * Spec-630 B17: con hx-boost el <head> no se recarga. Si la pestaña tiene estáticos
 * de otra versión, la próxima navegación carga la página entera (CSS nuevo incluido).
 */
test("con estáticos de otra versión, navegar carga la página entera", async ({ page }) => {
  await page.goto("/galeria");
  const marca = () => page.evaluate(() => (window as unknown as { __marca?: boolean }).__marca === true);

  // Mismo versión: hx-boost reemplaza el contenido y la ventana sigue siendo la misma.
  await page.evaluate(() => ((window as unknown as { __marca: boolean }).__marca = true));
  await page.getByRole("link", { name: "Nuevo relato" }).click();
  await expect(page).toHaveURL(/\/nuevo$/);
  expect(await marca()).toBe(true);

  // La pestaña «quedó vieja»: la próxima navegación es completa.
  await page.evaluate(() => {
    document.querySelector('meta[name="asset-version"]')!.setAttribute("content", "vieja");
  });
  await page.getByRole("link", { name: "Mis historias" }).click();
  await expect(page).toHaveURL(/\/galeria$/);
  await expect.poll(marca).toBe(false);
  await expect(page.locator('meta[name="asset-version"]')).not.toHaveAttribute("content", "vieja");
});
