import { test, expect, type Page } from "@playwright/test";

/**
 * Spec-530 S4: el asistente de autoría de punta a punta, con el LLM simulado del
 * arnés (responde JSON coherente para cada rol).
 */
test.describe.configure({ mode: "serial" });
test.skip(!!process.env.BASE_URL, "Crea historias: solo contra el arnés con DB descartable");

const guardado = (page: Page) => page.locator("[data-guardado]").first();
/** Espera a que termine el último guardado y haya salido bien (Spec-550 H6). */
async function guardadoListo(page: Page) {
  await expect(guardado(page)).not.toHaveAttribute("data-pendiente", "1");
  await expect(guardado(page)).toContainText("Guardado");
}
const modal = (page: Page) => page.locator("#asistente-analizando");

async function crearDesdeNuevo(page: Page, titulo: string, premisa = "José ve a una mujer muerta en el espejo del micro.") {
  await page.goto("/nuevo");
  await expect(page.getByRole("button", { name: /Analizar mi historia/ })).toBeDisabled();
  await page.getByLabel("Título").fill(titulo);
  if (premisa) await page.getByLabel("¿De qué trata?").fill(premisa);
  await expect(page).toHaveURL(/\/asistente\/[0-9a-f-]{36}\/direccion$/);
  await guardadoListo(page);
  return page.url().split("/")[4];
}

test("flujo completo: dirección → taller → escaleta → generar", async ({ page }) => {
  const sid = await crearDesdeNuevo(page, "E2E asistente");
  await page.getByText("Pavor creciente").click();
  await page.getByLabel("¿Cómo termina?").fill("Le deja flores y descansa en paz.");
  await page.getByLabel("Protagonista").fill("José");
  await guardadoListo(page);

  // Lo guardado sobrevive a recargar.
  await page.reload();
  await expect(page.getByLabel("¿Cómo termina?")).toHaveValue("Le deja flores y descansa en paz.");
  await expect(page.getByRole("radio", { name: /Pavor creciente/ })).toBeChecked();

  // La IA solo con el comando explícito, con el modal.
  await page.getByRole("button", { name: /Analizar mi historia/ }).click();
  await expect(page).toHaveURL(new RegExp(`/asistente/${sid}/taller$`));
  await expect(page.locator("[data-fin]")).toContainText("preguntas abiertas");
  await expect(page.locator('[data-pregunta="final"]')).toContainText(/a propósito/i);

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
  await guardadoListo(page);
  await page.reload();
  await expect(page.locator('form[data-number="1"] textarea[name="events"]').last()).toHaveValue(
    "José frena el micro de golpe.",
  );

  await page.locator('form[data-number="1"]').getByRole("button", { name: "Personaje" }).click();
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
  await guardadoListo(page);

  await page.reload();
  await expect(page.getByLabel("Tipo de horror")).toHaveValue("paranormal");
  await expect(page.getByLabel("Estilo")).toHaveValue("fantasmas");
  await expect(page.getByLabel("Qué es")).toHaveValue("espiritu");
  await expect(page.getByLabel("Qué quiere")).toHaveValue("Que José se detenga.");
});

// Bug (2026-09-27): con Tab desde «¿De qué trata?» a las tarjetas de efecto, la
// página quedaba en blanco. Los radios `sr-only` (absolutos) escapaban de su tarjeta
// y el navegador desplazaba el <body> (overflow-hidden) para mostrarlos. Solo debe
// scrollear <main>; la barra lateral y el formulario siguen a la vista.
test("navegar con Tab por las tarjetas no desplaza la página fuera de la vista", async ({ page }) => {
  await crearDesdeNuevo(page, "E2E tab");
  await page.getByLabel("¿De qué trata?").focus();

  const fueraDeLugar = () =>
    page.evaluate(() => ({
      html: document.documentElement.scrollTop,
      body: document.body.scrollTop,
      sidebar: Math.round(document.querySelector("aside")!.getBoundingClientRect().top),
    }));

  for (let i = 0; i < 12; i++) {
    await page.keyboard.press("Tab");
    expect(await fueraDeLugar()).toEqual({ html: 0, body: 0, sidebar: 0 });
  }
});

// Spec-550 H11: la barra fija lleva los pasos y las acciones; sigue arriba al scrollear.
test("la barra con los pasos y «Analizar» queda fija arriba al scrollear", async ({ page }) => {
  await crearDesdeNuevo(page, "E2E barra");
  const barra = page.locator(".asistente-barra");
  await expect(barra.getByRole("navigation", { name: "Pasos del asistente" })).toBeVisible();
  await expect(barra.getByRole("button", { name: /Analizar mi historia/ })).toBeEnabled();

  await page.locator("main").evaluate((m) => m.scrollTo(0, m.scrollHeight));
  await expect.poll(() => barra.evaluate((b) => Math.round(b.getBoundingClientRect().top))).toBe(0);
  await expect(barra.getByRole("button", { name: /Analizar mi historia/ })).toBeInViewport();
  await expect(barra.locator(".pasos-forge")).toBeInViewport();
});

// Spec-550 H6: el guardado se avisa con una notificación que se va sola; un error queda.
test("la notificación de guardado aparece y se va; un error queda hasta cerrarlo", async ({ page }) => {
  await crearDesdeNuevo(page, "E2E notificación");
  const aviso = page.locator("[data-guardado]");
  await page.getByLabel("Protagonista").fill("José");
  await expect(aviso).toHaveAttribute("data-estado", "ok");
  await expect(aviso).toBeVisible();
  await expect(aviso).toHaveAttribute("data-estado", "oculto", { timeout: 4000 });

  await page.route("**/api/v1/authoring/stories/*/direction", (r) => r.fulfill({ status: 500, body: '{"detail":"falla de prueba"}' }));
  await page.getByLabel("Protagonista").fill("José Pérez");
  await expect(aviso).toHaveAttribute("data-estado", "error");
  await page.waitForTimeout(2500);
  await expect(aviso).toHaveAttribute("data-estado", "error");
  await aviso.getByRole("button", { name: "Cerrar el aviso" }).click();
  await expect(aviso).toHaveAttribute("data-estado", "oculto");
});

// Spec-550 H8: rearmar la escaleta se confirma con el diálogo del tema.
test("rearmar la escaleta pide confirmación con el diálogo propio", async ({ page }) => {
  const sid = await crearDesdeNuevo(page, "E2E rearmar");
  for (const kind of ["consult", "plan_outline"]) {
    const job = (await (await page.request.post(`/api/v1/stories/${sid}/jobs`, { data: { kind } })).json()).job_id;
    await expect
      .poll(async () => (await (await page.request.get(`/api/v1/jobs/${job}`)).json()).status, { timeout: 20000 })
      .toBe("done");
  }
  await page.goto(`/asistente/${sid}/taller`);
  const dialogo = page.locator("#forge-confirm");
  const rearmar = page.getByRole("button", { name: /Rearmar la escaleta/ }).first();

  await rearmar.click();
  await expect(dialogo).toBeVisible();
  await expect(dialogo).toContainText("¿Rearmar la escaleta?");
  await dialogo.getByRole("button", { name: "Cancelar" }).click();
  await expect(dialogo).toBeHidden();
  await expect(modal(page)).toBeHidden();
  await expect(page).toHaveURL(new RegExp(`/asistente/${sid}/taller$`));

  await rearmar.click();
  await dialogo.getByRole("button", { name: "Rearmar la escaleta" }).click();
  await expect(page).toHaveURL(new RegExp(`/asistente/${sid}/escaleta$`), { timeout: 20000 });
});
