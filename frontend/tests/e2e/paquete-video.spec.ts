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
  const boton = page.locator("[data-acciones-version]:not(.hidden) [data-armar-guion]");
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

  await page.locator(`[data-acciones-version="${narrativeId}"] [data-armar-guion]`).click();
  await page.locator("#forge-confirm").getByRole("button", { name: "Armar el guion" }).click();

  await page.waitForURL(new RegExp(`/relatos/${narrativeId}/video$`), { timeout: 20_000 });
  await expect(page.locator("[data-bloque]").first()).toBeVisible();
  await page.locator('[data-tab="mapa"]').click();
  await expect(page.locator(".mapa-tramo").first()).toBeVisible();
  await page.locator('[data-tab="calabaza"]').click();
  await expect(page.locator('[data-calabaza="outro"]')).toHaveValue(/Buenas noches/);

  // De vuelta en los relatos, la variante ya tiene su paquete.
  await page.goto(`/historia/${STORY_ID}/relatos`);
  await expect(page.locator(`[data-para-el-video="${narrativeId}"]`)).toBeVisible();
  // Y en «Mis historias», la tarjeta lleva directo al guion.
  await page.goto("/galeria");
  await page.locator(`a[data-para-el-video="${narrativeId}"]`).click();
  await page.waitForURL(new RegExp(`/relatos/${narrativeId}/video$`));
});

// ── S3: la pantalla «Para el video» (§3.7.2) ────────────────────────────────

async function abrirVideo(page: import("@playwright/test").Page, tab = "") {
  await page.goto(`/historia/${STORY_ID}/relatos`);
  await page.locator("[data-acciones-version]:not(.hidden) [data-para-el-video]").click();
  await page.waitForURL(/\/video/);
  await page.locator("[data-video]").waitFor();
  await page.locator("[data-resumen] [data-lector]").first().waitFor(); // el script ya dibujó
  if (tab) await page.locator(`[data-tab="${tab}"]`).click();
}

async function esperarGuardado(page: import("@playwright/test").Page) {
  const aviso = page.locator("[data-guardado]");
  await expect(aviso).toHaveAttribute("data-estado", "ok", { timeout: 5_000 });
  await expect(aviso).not.toHaveAttribute("data-pendiente", "1");
}

test("guion: remarcar una palabra, la pausa y cómo se lee quedan guardados", async ({ page }) => {
  await abrirVideo(page);
  const bloque = page.locator("[data-bloque]").first();
  await bloque.locator(".palabra-video").nth(1).click();
  await expect(bloque.locator(".remarcado")).toHaveCount(1);
  await esperarGuardado(page);

  await page.locator('[data-pausa="0"][data-v="ninguna"]').click();
  await esperarGuardado(page);
  await bloque.locator("[data-indicacion]").fill("Más despacio, casi en susurro.");
  await esperarGuardado(page);

  await page.reload();
  const otra = page.locator("[data-bloque]").first();
  await expect(otra.locator(".remarcado")).toHaveCount(1);
  await expect(page.locator('[data-pausa="0"][data-v="ninguna"]')).toHaveAttribute("aria-pressed", "true");
  await expect(otra.locator("[data-indicacion]")).toHaveValue("Más despacio, casi en susurro.");

  // Sacarlo desde la lista de la derecha.
  await page.locator("[data-quitar]").first().click();
  await expect(page.locator("[data-bloque]").first().locator(".remarcado")).toHaveCount(0);
  await esperarGuardado(page);
});

test("quién lee se cambia y queda", async ({ page }) => {
  await abrirVideo(page);
  await page.locator('[data-lector="Yael"]').click();
  await esperarGuardado(page);
  await page.reload();
  await expect(page.locator('[data-lector="Yael"]')).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator('[data-panel="guion"]')).toContainText("Lo que lee Yael");
});

test("la calabaza: corregir la intro y bajar el .txt", async ({ page }) => {
  await abrirVideo(page, "calabaza");
  const intro = page.locator('[data-calabaza="intro"]');
  await intro.click();
  await page.keyboard.press("Control+A");
  await page.keyboard.type("Bienvenidos a mi cripta, esta noche hay ruta y bosque.");
  await esperarGuardado(page);

  const [descarga] = await Promise.all([page.waitForEvent("download"), page.locator("[data-bajar-txt]").click()]);
  expect(descarga.suggestedFilename()).toMatch(/^calabaza-.*\.txt$/);
  const fs = await import("fs");
  const texto = fs.readFileSync(await descarga.path(), "utf-8");
  expect(texto).toContain("INTRO\nBienvenidos a mi cripta, esta noche hay ruta y bosque.");
  expect(texto).toContain("OUTRO\n");
});

test("el mapa: cambiar el tipo y el prompt de un momento", async ({ page }) => {
  await abrirVideo(page, "mapa");
  await page.locator('.mapa-tramo[data-mom="1"]').click();
  await page.locator('[data-ficha="1"] [data-tipo="video"]').click();
  await esperarGuardado(page);
  const prompt = page.locator('[data-ficha="1"] [data-campo="prompt_imagen"]');
  await prompt.fill("An empty gas station at night under a flickering light, 16:9");
  await esperarGuardado(page);

  await page.reload();
  await page.locator('.mapa-tramo[data-mom="1"]').click();
  await expect(page.locator('[data-ficha="1"] [data-tipo="video"]')).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator('[data-ficha="1"] [data-campo="prompt_imagen"]')).toHaveValue(/gas station/);
  await expect(page.locator('[data-ficha="1"] [data-campo="prompt_movimiento"]')).toBeVisible();
});

test("si cambian los párrafos de un acto, avisa; armar de nuevo lo deja al día", async ({ page, request }) => {
  await abrirVideo(page);
  const narrativeId = (await page.locator("[data-video]").getAttribute("data-narrative-id")) as string;
  const actual = await (await request.get(`/api/v1/generated-narratives/${narrativeId}/text`)).json();
  const acto1 = actual.text.split(/^## Acto \d+\s*$/m)[1].trim();
  await request.put(`/api/v1/generated-narratives/${narrativeId}/acts/1`, {
    data: { text: `${acto1}\n\nUn párrafo nuevo que agregué.` },
  });

  await page.reload();
  await expect(page.locator("[data-avisos-paquete]")).toContainText("Cambió la cantidad de párrafos");
  await expect(page.locator('[data-pdf="guion"]')).toHaveAttribute("aria-disabled", "true");

  await page.locator("[data-rearmar]").click();
  await page.locator("#forge-confirm").getByRole("button", { name: "Armar de nuevo" }).click();
  await expect(page.locator("[data-avisos-paquete]")).not.toContainText("Cambió la cantidad", { timeout: 20_000 });
});

// ── S4: los PDF ─────────────────────────────────────────────────────────────

test("bajar el PDF del guion y el del mapa", async ({ page }) => {
  await abrirVideo(page);
  const [guion] = await Promise.all([page.waitForEvent("download"), page.locator('[data-pdf="guion"]').click()]);
  expect(guion.suggestedFilename()).toMatch(/^guion-.*\.pdf$/);
  const fs = await import("fs");
  expect(fs.readFileSync(await guion.path()).subarray(0, 5).toString()).toBe("%PDF-");

  await page.locator('[data-tab="mapa"]').click();
  const [mapa] = await Promise.all([page.waitForEvent("download"), page.locator('[data-pdf="mapa"]').click()]);
  expect(mapa.suggestedFilename()).toMatch(/^mapa-.*\.pdf$/);
});
