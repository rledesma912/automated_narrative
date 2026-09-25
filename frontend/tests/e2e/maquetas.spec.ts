import { test, expect } from "@playwright/test";

// Spec-530 S0: mientras la IA trabaja, un modal bloquea toda la página.
test.describe("Maquetas — modal de análisis", () => {
  test("Analizar abre el modal y deja la página inerte hasta cancelar", async ({ page }) => {
    await page.goto("/maquetas/direccion");
    const titulo = page.locator("#m-titulo");
    const modal = page.locator("#maqueta-analizando");

    await expect(modal).toBeHidden();
    await page.getByRole("button", { name: /Analizar mi historia/ }).click();

    await expect(modal).toBeVisible();
    await expect(page.getByRole("heading", { name: "Interpretando la historia…" })).toBeVisible();
    await expect(page.locator("main")).toHaveAttribute("inert", "");
    await expect(page.locator("aside")).toHaveAttribute("inert", "");

    // Con la página inerte no se puede escribir en los campos.
    const box = await titulo.boundingBox();
    await page.mouse.click(box!.x + 10, box!.y + 10);
    await page.keyboard.type("XYZ");
    await expect(titulo).toHaveValue("la pena del colectivo");

    await page.getByRole("button", { name: "Cancelar" }).click();
    await expect(modal).toBeHidden();
    await expect(page.locator("main")).not.toHaveAttribute("inert", "");
  });

  test("al terminar, el análisis lleva al paso siguiente", async ({ page }) => {
    await page.goto("/maquetas/taller");
    await page.getByRole("button", { name: /Armar la escaleta/ }).click();
    await expect(page.getByRole("heading", { name: "Armando la escaleta…" })).toBeVisible();
    await page.getByRole("button", { name: /Simular que terminó/ }).click();
    await expect(page).toHaveURL(/\/maquetas\/escaleta$/);
  });
});
