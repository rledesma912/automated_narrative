/**
 * Test: Sala de Generación — diagnóstico de bloqueo
 *
 * Verifica que la sala de generación:
 * 1. Carga correctamente (no queda en blanco)
 * 2. No tiene errores de sintaxis JS en el script block
 * 3. Hace el health-check al backend
 * 4. Abre la conexión EventSource al stream
 * 5. Muestra eventos de progreso (o error visible, nunca silencio)
 *
 * Para correr: cd frontend && npx playwright test tests/streaming_room.spec.ts
 */

import { test, expect } from "@playwright/test";

const FRONTEND = "http://localhost:3000";
const BACKEND  = "http://localhost:8010";

// ── Helpers ───────────────────────────────────────────────────────────────────

async function createStoryViaApi(): Promise<string> {
  const res = await fetch(`${BACKEND}/api/v1/stories`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: "Test Playwright - El Monte",
      protagonista: "Irene: narradora y protagonista",
      relator: "Primera persona en pasado. Narrador: Irene. Tono: intimista. Registro: rural_tradicional.",
      escenarios: "Casa de María: vivienda rural; Monte de los Espinillos: zona oscura",
      sinopsis: "Irene llega a la casa de su suegra. La tormenta los obliga a cruzar el monte.",
      atmosfera: "Folk Horror (rural_folklore) - creciente_opresivo",
      reglas: ["La tecnología de celulares no existe."],
      storyteller_config: {
        storyteller_id: "P1",
        storyteller_name: "Irene",
        voice_style: "intimista",
        voice: { person: "primera", tense: "pasado", style: "intimista" },
        atmosphere: { genre: "Folk Horror", subgenre: "rural_folklore", tone: "creciente_opresivo" },
        scenarios: [
          { id: "S1", order: 1, name: "Casa de María", description: "vivienda rural" },
          { id: "S2", order: 2, name: "Monte de los Espinillos", description: "zona oscura" },
        ],
        rules: [{ id: "R1", text: "La tecnología de celulares no existe.", type: "entorno" }],
        perception: { reliability: "subjetiva", distortion: { level: "media", triggers: ["miedo"] } },
        knowledge: { domain: { paranormal: "medio", religioso: "alto" }, interpretation_style: "simbolica" },
        language: { register: "rural_tradicional", figurative_density: "media" },
        bias: { fear_focus: ["proteccion_de_hijos"], attention_focus: ["sonidos"] },
      },
      personajes_full: [
        { id: "P1", name: "Irene", role: "narradora y protagonista", traits: ["religiosa"] },
      ],
    }),
  });
  const data = await res.json() as { id: string };
  return data.id;
}

// ── Tests ─────────────────────────────────────────────────────────────────────

test.describe("Sala de Generación", () => {

  test("1. la sala carga y el script no tiene errores de sintaxis", async ({ page }) => {
    const consoleErrors: string[] = [];
    const jsErrors: string[]      = [];

    page.on("console", msg => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    page.on("pageerror", err => jsErrors.push(err.message));

    const storyId = await createStoryViaApi();
    await page.goto(`${FRONTEND}/generar/stream/${storyId}`);
    await page.waitForTimeout(2000);

    console.log("Console errors:", consoleErrors);
    console.log("JS errors (pageerror):", jsErrors);

    // La sala debe cargar el contenedor principal
    await expect(page.locator("#streaming-root")).toBeVisible();

    // No debe haber errores de sintaxis JS
    const syntaxErrors = jsErrors.filter(e => e.toLowerCase().includes("syntaxerror") || e.toLowerCase().includes("unexpected"));
    expect(syntaxErrors, `SyntaxErrors en el script: ${syntaxErrors.join("\n")}`).toHaveLength(0);
  });

  test("2. el badge de conexión cambia de INICIANDO (JS corre)", async ({ page }) => {
    const storyId = await createStoryViaApi();
    await page.goto(`${FRONTEND}/generar/stream/${storyId}`);

    // Si el JS corre, el badge debe cambiar de INICIANDO a algo distinto en 3s
    await page.waitForTimeout(3000);
    const badge = page.locator("#connection-badge");
    const badgeText = await badge.textContent();
    console.log("Badge after 3s:", badgeText);

    expect(badgeText?.trim()).not.toBe("INICIANDO");
  });

  test("3. el health-check al backend dispara una request visible", async ({ page }) => {
    const healthRequests: string[] = [];
    page.on("request", req => {
      if (req.url().includes("health")) healthRequests.push(req.url());
    });

    const storyId = await createStoryViaApi();
    await page.goto(`${FRONTEND}/generar/stream/${storyId}`);
    await page.waitForTimeout(3000);

    console.log("Health requests intercepted:", healthRequests);
    expect(healthRequests.length, "No se hizo request al /health").toBeGreaterThan(0);
  });

  test("4. EventSource se abre al endpoint de stream del Core", async ({ page }) => {
    const streamRequests: string[] = [];
    page.on("request", req => {
      if (req.url().includes("/stream")) streamRequests.push(req.url());
    });

    const storyId = await createStoryViaApi();
    await page.goto(`${FRONTEND}/generar/stream/${storyId}`);
    await page.waitForTimeout(4000);

    console.log("Stream requests intercepted:", streamRequests);
    expect(streamRequests.length, "EventSource nunca se conectó al stream").toBeGreaterThan(0);
  });

  test("5. la sala muestra feedback visible (badge ≠ INICIANDO, o error panel)", async ({ page }) => {
    const storyId = await createStoryViaApi();
    await page.goto(`${FRONTEND}/generar/stream/${storyId}`);
    await page.waitForTimeout(5000);

    const badge       = (await page.locator("#connection-badge").textContent())?.trim();
    const errorHidden = await page.locator("#error-panel").evaluate(el => el.classList.contains("hidden"));
    const doneHidden  = await page.locator("#done-panel").evaluate(el => el.classList.contains("hidden"));

    console.log("Badge:", badge);
    console.log("Error panel hidden:", errorHidden);
    console.log("Done panel hidden:", doneHidden);

    // Al menos UNA cosa debe haber cambiado: badge ≠ INICIANDO, o un panel visible
    const somethingChanged = badge !== "INICIANDO" || !errorHidden || !doneHidden;
    expect(somethingChanged, `La sala sigue en estado inicial después de 5s. Badge="${badge}"`).toBe(true);
  });

});
