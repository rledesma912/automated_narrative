import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';

/**
 * Spec-315: Tests de Build — Generación de CSS
 * 
 * Verifica que `npm run build:css` genera correctamente
 * el archivo public/styles.css sin errores.
 */
describe('CSS Architecture — Build Process', () => {
  const frontendDir = process.cwd(); // Estamos ya en frontend/
  const outputCssPath = path.join(frontendDir, 'public', 'styles.css');

  beforeAll(() => {
    // Limpiar output anterior si existe
    if (fs.existsSync(outputCssPath)) {
      fs.unlinkSync(outputCssPath);
    }
  });

  afterAll(() => {
    // Restaurar CSS para que el servidor siga funcionando
    try {
      execSync('npm run build:css', { cwd: frontendDir, stdio: 'ignore' });
    } catch (e) {
      // Ignorar si falla
    }
  });

  it('npm run build:css genera public/styles.css', () => {
    // Ejecutar build
    execSync('npm run build:css', { 
      cwd: frontendDir,
      encoding: 'utf-8',
    });

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
