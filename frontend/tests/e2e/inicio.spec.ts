import { expect, test } from "@playwright/test";

/**
 * Spec-580 D7: el inicio entra entero en la pantalla (sin scroll), con el menú
 * abierto. D6: el diagnóstico salió del menú y se llega desde el pie.
 */
for (const viewport of [
  { width: 1366, height: 768 },
  { width: 1920, height: 1080 },
]) {
  test(`el inicio entra sin scroll a ${viewport.width}×${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.goto("/");
    await page.evaluate(() => localStorage.removeItem("forge:sidebar"));
    await page.reload();
    await expect(page.getByRole("heading", { name: "Contemos una historia de miedo" })).toBeVisible();
    const main = page.locator("main");
    const { scroll, client } = await main.evaluate((m) => ({ scroll: m.scrollHeight, client: m.clientHeight }));
    expect(scroll).toBeLessThanOrEqual(client);
    await expect(page.getByRole("link", { name: /Contar una historia nueva/ })).toBeInViewport();
  });
}

test("el diagnóstico no está en el menú: se llega desde el pie", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("aside").getByRole("link", { name: /API conn|Diagnóstico/ })).toHaveCount(0);
  await page.locator("#global-status-footer").getByRole("link", { name: "Diagnóstico técnico" }).click();
  await expect(page).toHaveURL(/\/debug$/);
});

test("el pie dice si la IA está lista, sin nombrar al Core", async ({ page }) => {
  await page.goto("/");
  const pie = page.locator("#global-status-footer");
  await expect(pie).toContainText("La IA está lista");
  await expect(pie).not.toContainText("Core");
});
