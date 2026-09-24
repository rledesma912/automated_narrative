import { test, expect } from "@playwright/test";

import { storyIdByTitle } from "./support/stories";

// Contra un frontend real (BASE_URL) se puede fijar la historia con TEST_STORY_ID.
let STORY_ID = process.env.TEST_STORY_ID || "";

test.describe("Vista de Relatos", () => {
  // Con el arnés propio (DB descartable) nos aseguramos de tener 2+ relatos para
  // probar el cambio de pestaña. Contra un frontend real (BASE_URL) no se crean datos.
  test.beforeAll(async ({ request }) => {
    if (!STORY_ID) STORY_ID = await storyIdByTitle(request, "El monte prohibido");
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

  // Spec-490 T2.4
  test("Descargar .md baja el relato para el TTS", async ({ page }) => {
    const panel = page.locator("[data-relato-panel].active").first();
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      panel.locator("[data-descargar-relato]").click(),
    ]);

    expect(download.suggestedFilename()).toMatch(/^el-monte-prohibido-\d{4}-\d{2}-\d{2}-\d{4}\.md$/);
    const stream = await download.createReadStream();
    let text = "";
    for await (const chunk of stream) text += chunk.toString("utf-8");
    expect(text.split("\n")[0]).toBe("# El monte prohibido");
    expect(text).toContain("## Acto 1");
  });

  test("Copiar Relato copia rótulos y prosa, sin el texto de los botones", async ({
    page,
    context,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    const panel = page.locator("[data-relato-panel].active").first();
    await panel.getByRole("button", { name: "Copiar Relato" }).click();
    await expect(panel.getByRole("button", { name: /Copiado/ })).toBeVisible();

    const copied = await page.evaluate(() => navigator.clipboard.readText());
    expect(copied).toMatch(/^Acto 1\n\n/);
    expect(copied).not.toContain("Regenerar");
  });
});

