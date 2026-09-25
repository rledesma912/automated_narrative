import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import express, { Express } from 'express';
import type { Server } from 'http';
import type { AddressInfo } from 'net';
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
  let baseUrl = '';

  const layoutLocals = {
    title: 'Test Page',
    activePage: 'home',
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

    // Puerto 0 → el SO asigna uno libre (no choca con `make ui` en 3010).
    await new Promise<void>((resolve) => {
      server = app.listen(0, '127.0.0.1', resolve);
    });
    baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
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
    expect(html).toMatch(/href="\/styles\.css(\?v=[^"]*)?"/); // versionado: ?v=<assetVersion>
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

  it('Spec-531: el layout no inyecta colores y el body usa los del tema', async () => {
    const html = await fetchHomeHtml();
    expect(html).not.toContain('--forge-bg:');
    expect(html).toMatch(/<body class="[^"]*bg-forge-bg text-forge-text/);
  });
});
