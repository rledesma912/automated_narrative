import { test, expect } from "@playwright/test";

/**
 * Wizard compacto para 1080p (Spec-440 §1, S5).
 * 1920×960 ≈ el área útil de un navegador en un monitor 1080p.
 */
test.describe("1920×960", () => {
  test.use({ viewport: { width: 1920, height: 960 } });

  test("paso 1: «Siguiente» visible sin scroll", async ({ page }, testInfo) => {
    await page.goto("/generar/paso/1");
    const siguiente = page.getByRole("button", { name: "Siguiente" });

    await expect(siguiente).toBeVisible();
    // El que scrollea es <main> (el body es h-screen overflow-hidden).
    const m = await page.evaluate(() => {
      const main = document.querySelector("main")!;
      const btn = [...document.querySelectorAll("button")].find((b) => /Siguiente/.test(b.textContent ?? ""))!;
      const pie = document.getElementById("global-status-footer")!;
      return {
        scrollHeight: main.scrollHeight,
        clientHeight: main.clientHeight,
        btnBottom: btn.getBoundingClientRect().bottom,
        pieTop: pie.getBoundingClientRect().top,
      };
    });
    expect(m.scrollHeight).toBeLessThanOrEqual(m.clientHeight);
    expect(m.btnBottom).toBeLessThanOrEqual(m.pieTop); // no queda tapado por el pie fijo

    await page.screenshot({ path: testInfo.outputPath("paso-1-1920x960.png") });
  });
});

test.describe("1366×768", () => {
  test.use({ viewport: { width: 1366, height: 768 } });

  for (const paso of [1, 2, 3, 4, 5]) {
    test(`paso ${paso}: sin scroll horizontal`, async ({ page }, testInfo) => {
      await page.goto(`/generar/paso/${paso}`);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow).toBeLessThanOrEqual(0);
      await page.screenshot({ path: testInfo.outputPath(`paso-${paso}-1366x768.png`), fullPage: true });
    });
  }
});
