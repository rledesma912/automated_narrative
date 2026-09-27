import { readFileSync } from "fs";
import path from "path";
import ejs from "ejs";
import { describe, it, expect } from "vitest";

const layoutPath = path.join(process.cwd(), "src/views/partials/layout.ejs");

describe("layout view", () => {
  // Spec-510 T1.2: el banner usa window.ForgeEta; los scripts defer respetan el orden.
  it("loads eta.js before generation-banner.js", () => {
    const template = readFileSync(layoutPath, "utf-8");
    const scripts = Array.from(
      template.matchAll(/<script src="\/js\/([\w-]+)\.js\?v=[^"]*" defer><\/script>/g),
      (m) => m[1],
    );

    expect(scripts).toContain("eta");
    expect(scripts.indexOf("eta")).toBeLessThan(scripts.indexOf("generation-banner"));
  });
});

// Spec-540 T1.3: dev se distingue de prod a simple vista; prod queda como siempre.
describe("layout según el ambiente", () => {
  const render = (environment?: object) =>
    ejs.renderFile(layoutPath, { title: "Inicio", activePage: "home", body: "<p>x</p>", environment });

  it("prod (sin environment): sin data-env, sin [DEV], vela de siempre y versión fija", async () => {
    const html = await render();
    expect(html.startsWith("<!DOCTYPE html>")).toBe(true);
    expect(html).not.toContain('data-env="dev"');
    expect(html).toContain("<title>NarrativeForge — Inicio</title>");
    expect(html).toContain('href="/favicon.svg"');
    expect(html).not.toContain("favicon-dev.svg");
    expect(html).not.toContain("data-env-badge");
    expect(html).toContain("v0.3.0 — Slice 3");
  });

  it("prod explícito se ve igual que sin environment", async () => {
    expect(await render({ env: "prod", isDev: false, branch: null, commit: null })).toBe(await render());
  });

  it("dev: tema, título, favicon, etiqueta y rama · commit", async () => {
    const html = await render({ env: "dev", isDev: true, branch: "feat/spec-540", commit: "4bdebc3" });
    expect(html).toContain('<html lang="es" data-env="dev">');
    expect(html).toContain("<title>[DEV] NarrativeForge — Inicio</title>");
    expect(html).toContain('href="/favicon-dev.svg"');
    expect(html).not.toContain('href="/favicon.svg"');
    expect(html).toContain('content="#eff1f5"');
    expect(html).toContain("data-env-badge");
    expect(html).toMatch(/DEV<\/span> · feat\/spec-540 · <code>4bdebc3<\/code>/);
    expect(html).not.toContain("v0.3.0 — Slice 3");
  });

  it("dev sin git legible: lo dice en vez de fallar", async () => {
    const html = await render({ env: "dev", isDev: true, branch: null, commit: null });
    expect(html).toMatch(/DEV<\/span> · sin git/);
  });
});
