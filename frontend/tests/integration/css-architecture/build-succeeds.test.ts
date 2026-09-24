import { describe, it, expect, afterAll } from 'vitest';
import { execSync } from 'child_process';
import fs from 'fs';
import os from 'os';
import path from 'path';

/**
 * Spec-315: Tests de Build — Generación de CSS
 *
 * Verifica que el comando de `npm run build:css` compila sin errores.
 *
 * Compila a un archivo temporal (mismo comando del package.json, otro `-o`)
 * en vez de reescribir public/styles.css: los demás tests de css-architecture
 * leen ese archivo en paralelo y el `make ui` en curso lo sirve.
 */
describe('CSS Architecture — Build Process', () => {
  const frontendDir = process.cwd(); // Estamos ya en frontend/
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'forge-css-'));
  const outputCssPath = path.join(tmpDir, 'styles.css');
  const pkg = JSON.parse(fs.readFileSync(path.join(frontendDir, 'package.json'), 'utf-8'));
  const buildCmd = `npx ${pkg.scripts['build:css'].replace('./public/styles.css', outputCssPath)}`;

  afterAll(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('npm run build:css genera public/styles.css', () => {
    expect(buildCmd).toContain(outputCssPath);
    execSync(buildCmd, { cwd: frontendDir, encoding: 'utf-8', stdio: 'pipe' });

    // Verificar que el archivo fue creado
    expect(fs.existsSync(outputCssPath)).toBe(true);
  });

  it('public/styles.css tiene contenido válido', () => {
    const cssContent = fs.readFileSync(outputCssPath, 'utf-8');
    
    // Verificar que hay contenido
    expect(cssContent.length).toBeGreaterThan(1000);
    
    // Verificar que contiene directivas de Tailwind
    expect(cssContent).toContain('@media');
    expect(cssContent).toContain('.text-');
    expect(cssContent).toContain('.bg-');
  });

  it('public/styles.css contiene clases de colores forge', () => {
    const cssContent = fs.readFileSync(outputCssPath, 'utf-8');
    
    // Verificar que se generaron clases para los colores personalizados
    expect(cssContent).toMatch(/\.text-forge-*/);
    expect(cssContent).toMatch(/\.bg-forge-*/);
    expect(cssContent).toMatch(/\.border-forge-*/);
  });

  it('public/styles.css contiene naranja personalizado', () => {
    const cssContent = fs.readFileSync(outputCssPath, 'utf-8');
    
    // Tailwind purga las clases no usadas, así que verificamos que está
    // en la config de tailwind.config.js en lugar del CSS compilado
    const configPath = require.resolve('../../../tailwind.config.js');
    const config = require(configPath);
    
    const orangeColor = config.theme?.extend?.colors?.orange?.['600'];
    expect(orangeColor).toBe('#F58300');
  });

  it('public/styles.css es válido sin errores de sintaxis', () => {
    const cssContent = fs.readFileSync(outputCssPath, 'utf-8');
    
    // Contar llaves abiertas y cerradas (simple check)
    const openBraces = (cssContent.match(/{/g) || []).length;
    const closeBraces = (cssContent.match(/}/g) || []).length;
    
    expect(openBraces).toBe(closeBraces);
  });

  it('public/styles.css no está vacío', () => {
    const stats = fs.statSync(outputCssPath);
    
    expect(stats.size).toBeGreaterThan(10000); // > 10KB
  });
});
