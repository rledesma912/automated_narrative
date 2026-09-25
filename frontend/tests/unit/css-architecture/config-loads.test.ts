import { describe, it, expect } from 'vitest';
import path from 'path';

/**
 * Spec-315: Tests Unitarios — Configuración CSS
 * 
 * Verifica que tailwind.config.js carga correctamente y tiene
 * la estructura esperada.
 */
describe('CSS Architecture — Config Validation', () => {
  it('tailwind.config.js carga sin errores', () => {
    // Resolver path dinámicamente (process.cwd() es frontend/)
    const configPath = path.join(process.cwd(), 'tailwind.config.js');
    
    // require() carga el módulo
    const config = require(configPath);
    
    expect(config).toBeDefined();
    expect(config.content).toBeDefined();
    expect(config.theme).toBeDefined();
  });

  it('tailwind.config.js tiene colores forge definidos', () => {
    const configPath = path.join(process.cwd(), 'tailwind.config.js');
    const config = require(configPath);
    
    const forgeColors = config.theme?.extend?.colors?.forge;
    expect(forgeColors).toBeDefined();
    
    // Spec-531: cada color apunta a su variable y admite opacidad (<alpha-value>).
    for (const name of ['bg', 'surface', 'accent', 'text', 'on-accent', 'error-bg', 'warning']) {
      expect(forgeColors[name]).toContain(`var(--forge-${name})`);
      expect(forgeColors[name]).toContain('<alpha-value>');
    }
    expect(config.theme?.extend?.colors?.orange).toBeUndefined();
  });

  it('tailwind.config.js define fontFamily', () => {
    const configPath = path.join(process.cwd(), 'tailwind.config.js');
    const config = require(configPath);
    
    const fonts = config.theme?.extend?.fontFamily;
    expect(fonts).toBeDefined();
    expect(fonts.serif).toContain('Georgia');
    // El font mono está con comillas en el string JSON: '"Courier New"'
    expect(JSON.stringify(fonts.mono)).toContain('Courier New');
  });

  it('postcss.config.js carga sin errores', () => {
    const configPath = path.join(process.cwd(), 'postcss.config.js');
    const config = require(configPath);
    
    expect(config).toBeDefined();
    expect(config.plugins).toBeDefined();
    expect(config.plugins.tailwindcss).toBeDefined();
    expect(config.plugins.autoprefixer).toBeDefined();
  });
});
