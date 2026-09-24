import { test, expect, type Page } from "@playwright/test";
import { storyIdByTitle } from "./support/stories";

/**
 * Banda de generación + canal global (Spec-460 S5).
 *
 * Arnés de playwright.config.ts (Core con DB descartable + LLM mock con demora).
 * El job se lanza por API, como si viniera de otra pestaña: la página tiene que
 * enterarse sola, sin polling.
 */
let STORY_ID = ""; // "La ofrenda" de la semilla
test.beforeAll(async ({ request }) => {
  STORY_ID = await storyIdByTitle(request, "La ofrenda");
});

test.describe.configure({ mode: "serial" });
test.skip(!!process.env.BASE_URL, "Genera historias: solo contra el arnés con DB descartable");

function trackRequests(page: Page): string[] {
  const urls: string[] = [];
  page.on("request", (r) => urls.push(new URL(r.url()).pathname));
  return urls;
}

async function startJobFromAnotherTab(page: Page): Promise<string> {
  const resp = await page.request.post(`/api/v1/stories/${STORY_ID}/jobs`, {
    data: { kind: "full_generation" },
  });
  expect(resp.status()).toBe(202);
  return (await resp.json()).job_id;
}

const banner = (page: Page) => page.locator("#generation-banner");
const running = (page: Page) => page.locator('#generation-banner [data-banner-state="running"]');

test("sin generaciones no aparece la banda ni hay polling", async ({ page }) => {
  const requests = trackRequests(page);
  await page.goto("/galeria");

  await expect(page.locator("#core-status-dot")).toHaveClass(/bg-green-500/); // snapshot recibido
  await page.waitForTimeout(3_000);

  await expect(banner(page)).toBeHidden();
  await expect(page.locator("[data-forge-jobs-dot]")).toBeHidden();
  await expect(page.locator("body")).not.toContainText(/generando:/i);
  expect(requests.filter((p) => p === "/api/v1/events")).toHaveLength(1);
  expect(requests.filter((p) => p.startsWith("/internal/"))).toHaveLength(0);
  expect(requests.filter((p) => p === "/api/v1/stories")).toHaveLength(0);
});

test("la banda aparece en vivo, avanza, sobrevive a la navegación y termina", async ({ page }) => {
  const requests = trackRequests(page);
  await page.goto("/galeria");
  await expect(page.locator("#core-status-dot")).toHaveClass(/bg-green-500/);

  await startJobFromAnotherTab(page);

  await expect(running(page)).toBeVisible({ timeout: 1_000 });
  await expect(running(page)).toContainText("«La ofrenda»");
  await expect(page.locator("[data-forge-jobs-dot]")).toBeVisible();
  const link = running(page).locator("[data-banner-link]");
  await expect(link).toHaveAttribute("href", `/generar/stream/${STORY_ID}`);
  await expect(running(page).locator("[data-banner-step]")).toContainText(/Acto \d de 5/, {
    timeout: 5_000,
  });

  // Navegación hx-boost: el body cambia pero la conexión y el estado siguen.
  await page.locator("aside a[href='/']").click();
  await expect(page).toHaveURL(/\/$/);
  await expect(running(page)).toBeVisible();

  const done = page.locator('#generation-banner [data-banner-state="done"]');
  await expect(done).toBeVisible({ timeout: 30_000 });
  await expect(done).toContainText("«La ofrenda» está lista");
  await expect(done.locator("[data-banner-link]")).toHaveAttribute(
    "href",
    `/historia/${STORY_ID}/relatos`,
  );
  await expect(page.locator("[data-forge-jobs-dot]")).toBeHidden();
  await expect(page.locator("#footer-last-event")).toContainText("«La ofrenda»: lista");

  await done.locator("[data-banner-close]").click();
  await expect(banner(page)).toBeHidden();
  expect(requests.filter((p) => p === "/api/v1/events")).toHaveLength(1);
});

test("«Ver progreso» lleva a la sala del job en curso", async ({ page }) => {
  await page.goto("/galeria");
  await expect(page.locator("#core-status-dot")).toHaveClass(/bg-green-500/);
  const jobId = await startJobFromAnotherTab(page);
  await expect(running(page)).toBeVisible({ timeout: 1_000 });

  await running(page).locator("[data-banner-link]").click();

  await expect(page).toHaveURL(new RegExp(`/generar/stream/${STORY_ID}$`));
  expect(
    await page.evaluate(() => (window as unknown as { ACTIVE_JOB_ID: string }).ACTIVE_JOB_ID),
  ).toBe(jobId);
  await expect(banner(page)).toBeHidden(); // en la sala no se muestra
  await expect(page.locator("#status-line")).toHaveText("Historia generada con éxito", {
    timeout: 30_000,
  });
});
