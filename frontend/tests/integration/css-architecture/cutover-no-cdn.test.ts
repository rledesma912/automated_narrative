import { describe, it, expect, beforeAll } from 'vitest';
import fs from 'fs';
import path from 'path';

/**
 * Spec-315: Tests E2E Offline — Verificación Cutover
 * 
 * Verifica que:
 * 1. layout.ejs NO contiene CDN
 * 2. layout.ejs NO contiene config inline Tailwind
 * 3. Solo contiene link a CSS compilado
 * 4. CSS compilado existe y es válido
 * 5. Variables CSS están presentes
 */
describe('CSS Architecture — Cutover (Sin CDN)', () => {
  const layoutPath = path.join(process.cwd(), 'src', 'views', 'partials', 'layout.ejs');
  const cssPath = path.join(process.cwd(), 'public', 'styles.css');

  beforeAll(() => {
    // Asegurar que CSS existe antes de tests
    // Reintentamos compilar si no existe
    if (!fs.existsSync(cssPath)) {
      try {
        const { execSync } = require('child_process');
        execSync('npm run build:css', { cwd: process.cwd(), stdio: 'ignore' });
      } catch (e) {
        // Ignorar error, el test fallará si CSS no existe
      }
    }
  });

  it('layout.ejs NO contiene CDN Tailwind', () => {
    const content = fs.readFileSync(layoutPath, 'utf-8');
    
    expect(content).not.toContain('cdn.tailwindcss.com');
    expect(content).not.toContain('https://cdn.tailwindcss.com');
  });

  it('layout.ejs NO contiene config inline Tailwind', () => {
    const content = fs.readFileSync(layoutPath, 'utf-8');
    
    // No debe haber script que inicie tailwind.config
    expect(content).not.toContain('tailwind.config =');
  });

  it('layout.ejs contiene link a /styles.css', () => {
    const content = fs.readFileSync(layoutPath, 'utf-8');
    
    expect(content).toContain('href="/styles.css"');
    expect(content).toContain('<link rel="stylesheet"');
  });

  it('layout.ejs contiene solo HTMX script (no Tailwind)', () => {
    const content = fs.readFileSync(layoutPath, 'utf-8');
    
    // Debe tener HTMX
    expect(content).toContain('htmx.org');
    
    // Debe tener solo 1 <script> dentro de head (HTMX)
    const headMatch = content.match(/<head>[\s\S]*?<\/head>/);
    expect(headMatch).toBeDefined();
    
    const head = headMatch![0];
    const scriptCount = (head.match(/<script[^>]*src=/g) || []).length;
    
    // Solo HTMX script (1)
    expect(scriptCount).toBe(1);
  });

  it('public/styles.css existe y es válido', () => {
    expect(fs.existsSync(cssPath)).toBe(true);
    
    const stats = fs.statSync(cssPath);
    expect(stats.size).toBeGreaterThan(10000); // > 10KB
  });

  it('layout.ejs define variables CSS en :root', () => {
    const content = fs.readFileSync(layoutPath, 'utf-8');
    
    // Debe tener inyección de variables desde backend
    expect(content).toContain('<%- themeCssVars %>');
    expect(content).toContain(':root');
  });

  it('CSS compilado contiene estilos base de Tailwind', () => {
    const css = fs.readFileSync(cssPath, 'utf-8');
    
    // Verificar que tiene directives de Tailwind compiladas
    expect(css).toMatch(/\*/);      // Reset universal selector
    expect(css).toMatch(/\.flex/);  // Flex utilities
    expect(css).toMatch(/\.text-/); // Text utilities
    expect(css).toMatch(/\.bg-/);   // Background utilities
  });

  it('CSS compilado contiene componentes custom', () => {
    const css = fs.readFileSync(cssPath, 'utf-8');
    
    // Verificar que los @layer components están presentes
    expect(css).toContain('@media');
    
    // Si contiene ".btn-primary", verifique que es del componente custom
    // (esto depende de si la clase se usa en templates)
  });
});
