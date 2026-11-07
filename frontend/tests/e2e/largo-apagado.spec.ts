import { test, expect } from "@playwright/test";

/**
 * Spec-740 C6: con el largo deshabilitado (`LLM_PROFILE_MEDIO=off`, sin crédito para la IA
 * del largo) solo se escriben cortos. Corre con el arnés en ese modo:
 *   E2E_LLM_PROFILE_MEDIO=off npx playwright test largo-apagado
 */
test.describe.configure({ mode: "serial" });
test.skip(
  !!process.env.BASE_URL || process.env.E2E_LLM_PROFILE_MEDIO !== "off",
  "Solo con el arnés y E2E_LLM_PROFILE_MEDIO=off",
);

const NOTA = "Por ahora solo se pueden escribir relatos cortos.";
let largo = "";

test("un relato nuevo solo puede ser corto", async ({ page }) => {
  await page.goto("/nuevo");
  await expect(page.getByRole("radio", { name: /Media/ })).toBeDisabled();
  await expect(page.getByRole("radio", { name: /Corto/ })).toBeChecked();
  await expect(page.locator("[data-largo-nota='medio']")).toContainText(NOTA);
});

test("una historia larga avisa y sus botones de IA no hacen nada", async ({ page, request }) => {
  const stories = await (await request.get("/api/v1/stories")).json();
  largo = stories.find((s: { structure: string }) => s.structure === "medio").id;

  await page.goto(`/asistente/${largo}/taller`);
  const nota = page.locator(".asistente-barra [data-ia-apagada-nota]");
  await expect(nota).toContainText(NOTA);

  const boton = page.locator(".asistente-barra [data-analizar]").first();
  await expect(boton).toBeDisabled();
  // Aunque un script lo vuelva a habilitar, el clic no lanza nada (el guardia de clic).
  await boton.evaluate((b) => ((b as HTMLButtonElement).disabled = false));
  await boton.click();
  await expect(page.locator("[data-ia-modal], dialog[open]")).toHaveCount(0);
  const activo = await request.get(`/api/v1/stories/${largo}/jobs/active`);
  expect(activo.status()).toBe(404);

  // La API, de todos modos, dice que no.
  const resp = await request.post(`/api/v1/stories/${largo}/jobs`, { data: { kind: "consult" } });
  expect(resp.status()).toBe(409);
  expect((await resp.json()).detail).toBe(NOTA);
});

test("«Pasarla a corto» lleva al largo y, al cambiarlo, la IA vuelve", async ({ page }) => {
  await page.goto(`/asistente/${largo}/escaleta`);
  await page.locator("[data-ia-apagada-nota]").getByRole("link", { name: "Pasarla a corto" }).click();
  await expect(page).toHaveURL(new RegExp(`/asistente/${largo}/direccion#largo$`));

  await page.getByText("Corto", { exact: true }).click();
  // La historia ya tenía actos (largos): se borran, así que se pregunta antes.
  await page.locator("dialog[open]").getByRole("button", { name: "Cambiar el largo" }).click();
  await expect(page.locator("[data-ia-apagada-nota]")).toHaveCount(0);
  await expect(page.locator(".asistente-barra [data-analizar]").first()).toBeEnabled();
});
