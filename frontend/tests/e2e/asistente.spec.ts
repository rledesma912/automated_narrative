import { test, expect, type Page } from "@playwright/test";

/**
 * Spec-530 S4: el asistente de autoría de punta a punta, con el LLM simulado del
 * arnés (responde JSON coherente para cada rol).
 */
test.describe.configure({ mode: "serial" });
test.skip(!!process.env.BASE_URL, "Crea historias: solo contra el arnés con DB descartable");

const guardado = (page: Page) => page.locator("[data-guardado]").first();
const modal = (page: Page) => page.locator("#asistente-analizando");

async function crearDesdeNuevo(page: Page, titulo: string, premisa = "José ve a una mujer muerta en el espejo del micro.") {
  await page.goto("/nuevo");
  await expect(page.getByRole("button", { name: /Analizar mi historia/ })).toBeDisabled();
  await page.getByLabel("Título").fill(titulo);
  if (premisa) await page.getByLabel("¿De qué trata?").fill(premisa);
  await expect(page).toHaveURL(/\/asistente\/[0-9a-f-]{36}\/direccion$/);
  await expect(guardado(page)).toContainText("Guardado hace un momento");
  return page.url().split("/")[4];
}

test("flujo completo: dirección → taller → escaleta → generar", async ({ page }) => {
  const sid = await crearDesdeNuevo(page, "E2E asistente");
  await page.getByText("Pavor creciente").click();
  await page.getByLabel("¿Cómo termina?").fill("Le deja flores y descansa en paz.");
  await page.getByText("Es así a propósito: no lo cambies").click();
  await page.getByLabel("Protagonista").fill("José");
  await expect(guardado(page)).toContainText("Guardado hace un momento");

  // Lo guardado sobrevive a recargar.
  await page.reload();
  await expect(page.getByLabel("¿Cómo termina?")).toHaveValue("Le deja flores y descansa en paz.");
  await expect(page.getByRole("radio", { name: /Pavor creciente/ })).toBeChecked();

  // La IA solo con el comando explícito, con el modal.
  await page.getByRole("button", { name: /Analizar mi historia/ }).click();
  await expect(page).toHaveURL(new RegExp(`/asistente/${sid}/taller$`));
  await expect(page.locator("[data-fin]")).toContainText("preguntas abiertas");
  await expect(page.locator('[data-pregunta="final"]')).toContainText("a propósito");

  // Responder una pregunta y delegar otra.
  const meta = page.locator('[data-pregunta="meta"]');
  await meta.getByText("Primera opción (meta)").click();
  await meta.getByRole("button", { name: "Guardar respuesta" }).click();
  await expect(page.locator('li[data-pregunta="meta"]')).toContainText("Primera opción (meta)");
  const secreta = page.locator('article[data-pregunta="historia_secreta"]');
  await secreta.getByText("Escribir la mía…").click();
  await secreta.locator("[data-texto-mia]").fill("Él no paró aquella noche.");
  await secreta.getByRole("button", { name: "Guardar respuesta" }).click();
  await expect(page.locator('li[data-pregunta="historia_secreta"]')).toContainText("Él no paró aquella noche.");
  await page.locator('article[data-pregunta="en_juego"]').getByRole("button", { name: /Decidí vos/ }).click();
  await expect(page.locator('li[data-pregunta="en_juego"]')).toContainText("Primera opción (en_juego)");

  // Escaleta.
  await page.getByRole("button", { name: /Armar la escaleta/ }).click();
  await expect(page).toHaveURL(new RegExp(`/asistente/${sid}/escaleta$`));
  await expect(page.getByRole("heading", { name: "Acto 5 · Desenlace" })).toBeVisible();

  const acto2 = page.locator('form[data-number="2"]');
  await expect(acto2).toContainText("El encuentro del acto 2 repite el del acto 1.");
  await acto2.getByRole("button", { name: "Ignorar" }).click();
  await expect(page.locator('form[data-number="2"]')).not.toContainText("repite el del acto 1");

  const acto1 = page.locator('form[data-number="1"]');
  await acto1.getByRole("button", { name: /Agregar hecho/ }).click();
  await acto1.locator('textarea[name="events"]').last().fill("José frena el micro de golpe.");
  await expect(guardado(page)).toContainText("Guardado hace un momento");
  await page.reload();
  await expect(page.locator('form[data-number="1"] textarea[name="events"]').last()).toHaveValue(
    "José frena el micro de golpe.",
  );

  await page.locator('form[data-number="1"]').getByRole("button", { name: "+ personaje" }).click();
  await page.locator('form[data-number="1"] [data-p-nombre]').fill("El sereno");
  await page.locator('form[data-number="1"] [data-p-relacion]').fill("Lo conozco de vista");
  await page.locator('form[data-number="1"]').getByRole("button", { name: "Sumar al elenco" }).click();
  await expect(page.locator('form[data-number="1"]').getByRole("checkbox", { name: /El sereno/ })).toBeChecked();
  await expect(page.locator('form[data-number="2"]').getByRole("checkbox", { name: /El sereno/ })).not.toBeChecked();

  await expect(page.getByRole("link", { name: /Generar relato/ })).toHaveAttribute("href", `/generar/stream/${sid}`);
});

test("si la IA no puede empezar, el modal lo dice y se cierra", async ({ page }) => {
  await crearDesdeNuevo(page, "E2E sin premisa", "");
  await page.getByRole("button", { name: /Analizar mi historia/ }).click();

  await expect(modal(page)).toBeVisible();
  await expect(modal(page)).toContainText("Falta contar de qué trata la historia");
  await page.getByRole("button", { name: "Cerrar" }).click();
  await expect(modal(page)).toBeHidden();
  await expect(page.locator("main")).not.toHaveAttribute("inert", "");
});

test("la galería edita las historias del asistente en el asistente", async ({ page }) => {
  await page.goto("/galeria");
  const card = page.locator("[data-story-card]", { has: page.getByRole("heading", { name: "E2E asistente" }) });
  await expect(card.getByRole("link", { name: /Editar/ })).toHaveAttribute("href", /\/asistente\/.+\/direccion$/);
  await expect(page.getByRole("link", { name: "Nuevo relato" })).toHaveAttribute("href", "/nuevo");
});

test("género → estilo y la amenaza dependen del catálogo y se guardan", async ({ page }) => {
  await crearDesdeNuevo(page, "E2E amenaza");
  const estilo = page.getByLabel("Estilo");
  const naturaleza = page.getByLabel("Qué es");
  await expect(estilo).toBeDisabled();

  await page.getByLabel("Tipo de horror").selectOption("paranormal");
  await expect(estilo).toBeEnabled();
  await estilo.selectOption("fantasmas");
  await page.getByText("La amenaza").click();
  await expect(naturaleza).toBeEnabled();
  await naturaleza.selectOption("espiritu");
  await page.getByLabel("Qué quiere").fill("Que José se detenga.");
  await expect(guardado(page)).toContainText("Guardado hace un momento");

  await page.reload();
  await expect(page.getByLabel("Tipo de horror")).toHaveValue("paranormal");
  await expect(page.getByLabel("Estilo")).toHaveValue("fantasmas");
  await expect(page.getByLabel("Qué es")).toHaveValue("espiritu");
  await expect(page.getByLabel("Qué quiere")).toHaveValue("Que José se detenga.");
});
