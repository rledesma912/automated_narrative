import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import express, { Express } from 'express';
import type { Server } from 'http';
import path from 'path';

/**
 * Spec-315: Tests E2E — Render del layout estándar + carga de CSS
 *
 * Verifica que `partials/layout.ejs` produce HTML válido con:
 *   1. Link a /styles.css
 *   2. CDN fallback de Tailwind
 *   3. Config inline de Tailwind con la paleta forge
 *   4. Variables CSS forge en :root
 *
 * Renderiza el layout directamente (sin depender de una vista concreta)
 * para aislar el contrato del chrome del resto del frontend.
 */
describe('CSS Architecture — Layout Rendering', () => {
  let app: Express;
  let server: Server;
  const baseUrl = 'http://localhost:3010';

  const layoutLocals = {
    title: 'Test Page',
    themeFont: 'serif',
    themeCssVars:
      '--forge-bg: #1a1a1a; --forge-text: #ffffff; --forge-accent: #8b0000;' +
      ' --forge-surface: #2d2d2d; --forge-border: #444444; --forge-muted: #999999;',
    activePage: 'home',
    activeTheme: 'dark',
    allThemes: [
      { key: 'dark', def: { name: 'Dark', accent: '#8b0000' } },
      { key: 'light', def: { name: 'Light', accent: '#e0a0a0' } },
    ],
    body: '<div id="page-body">Layout test body</div>',
  };

  beforeAll(async () => {
    app = express();

    const viewsDir = path.join(process.cwd(), 'src', 'views');
    app.set('view engine', 'ejs');
    app.set('views', viewsDir);

    app.use(express.static(path.join(process.cwd(), 'public')));

    app.get('/', (_req, res) => {
      res.render('partials/layout', layoutLocals);
    });

    await new Promise<void>((resolve) => {
      server = app.listen(3010, resolve);
    });
  });

  afterAll(async () => {
    if (server) {
      await new Promise<void>((resolve, reject) => {
        server.close((err) => (err ? reject(err) : resolve()));
      });
    }
  });

  async function fetchHomeHtml(): Promise<string> {
    const response = await fetch(baseUrl + '/');
    expect(response.status).toBe(200);
    return response.text();
  }

  it('GET / retorna HTML válido con el body inyectado', async () => {
    const html = await fetchHomeHtml();
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<html');
    expect(html).toContain('</html>');
    expect(html).toContain('Layout test body');
  });

  it('layout.ejs incluye link a /styles.css', async () => {
    const html = await fetchHomeHtml();
    expect(html).toContain('href="/styles.css"');
  });

  it('layout.ejs ya no incluye CDN fallback de Tailwind (Arquitectura Offline-First)', async () => {
    const html = await fetchHomeHtml();
    expect(html).not.toContain('cdn.tailwindcss.com');
  });

  it('layout.ejs ya no incluye config inline de Tailwind (Configuración centralizada)', async () => {
    const html = await fetchHomeHtml();
    expect(html).not.toContain('tailwind.config');
    expect(html).not.toContain('colors: {');
  });

  it('layout.ejs define las variables CSS forge en :root', async () => {
    const html = await fetchHomeHtml();
    expect(html).toContain('--forge-bg:');
    expect(html).toContain('--forge-text:');
    expect(html).toContain('--forge-accent:');
  });
});
