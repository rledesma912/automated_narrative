import { test, expect } from "@playwright/test";

const STORY_ID = process.env.TEST_STORY_ID || "af608048-88a0-4234-b756-8867c1b64092";

test.describe("Vista de Relatos", () => {
  // Con el arnés propio (DB descartable) nos aseguramos de tener 2+ relatos para
  // probar el cambio de pestaña. Contra un frontend real (BASE_URL) no se crean datos.
  test.beforeAll(async ({ request }) => {
    if (process.env.BASE_URL) return;
    const list = await request.get(`/api/v1/story-templates/${STORY_ID}/narratives`);
    const relatos = (await list.json()) as unknown[];
    for (let i = relatos.length; i < 2; i++) {
      const created = await request.post(
        `/api/v1/story-templates/${STORY_ID}/generate-narrative?title=${encodeURIComponent(`E2E ${i + 1}`)}`,
      );
      expect(created.ok()).toBeTruthy();
    }
  });

  test.beforeEach(async ({ page }) => {
    await page.goto(`/historia/${STORY_ID}/relatos`);
    // No "networkidle": el canal global de eventos (Spec-460) mantiene una
    // conexión SSE abierta en todas las páginas, así que la red nunca queda ociosa.
    await page.locator("[data-relato-panel]").first().waitFor();
  });

  test("primer panel tiene clase active al cargar", async ({ page }) => {
    const firstPanel = page.locator("[data-relato-panel]").first();
    await expect(firstPanel).toHaveClass(/active/);
  });

  test("al hacer click en tab, ese panel se activa y los demás no", async ({ page }) => {
    const tabs = page.locator("[data-relato-tab]");
    const panels = page.locator("[data-relato-panel]");
    const count = await tabs.count();

    if (count < 2) {
      test.skip();
    }

    const tab2 = tabs.nth(1);
    const panel2 = panels.nth(1);

    await tab2.click();

    await expect(panel2).toHaveClass(/active/, { timeout: 2000 });
    await expect(panel2).not.toHaveClass(/hidden/);

    const panel1 = panels.nth(0);
    await expect(panel1).not.toHaveClass(/active/);
  });

  test("el panel activo tiene borde visible (css)", async ({ page }) => {
    const activePanel = page.locator("[data-relato-panel].active").first();
    await expect(activePanel).toHaveClass(/active/, { timeout: 3000 });

    const styles = await activePanel.evaluate((el) => {
      const cs = window.getComputedStyle(el);
      return {
        border: cs.border,
        outline: cs.outline,
        boxShadow: cs.boxShadow,
      };
    });

    const hasBorder = styles.border !== "0px none" && styles.border !== "none";
    const hasOutline = styles.outline !== "none";
    const hasShadow = styles.boxShadow !== "none" && styles.boxShadow !== "";

    expect(hasBorder || hasOutline || hasShadow).toBeTruthy();
  });
});