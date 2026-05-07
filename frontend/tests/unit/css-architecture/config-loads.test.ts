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
    
    // Verificar colores clave
    expect(forgeColors.bg).toBe('var(--forge-bg)');
    expect(forgeColors.surface).toBe('var(--forge-surface)');
    expect(forgeColors.accent).toBe('var(--forge-accent)');
    expect(forgeColors.text).toBe('var(--forge-text)');
  });

  it('tailwind.config.js tiene naranja 600 personalizado', () => {
    const configPath = path.join(process.cwd(), 'tailwind.config.js');
    const config = require(configPath);
    
    const orangeColors = config.theme?.extend?.colors?.orange;
    expect(orangeColors).toBeDefined();
    expect(orangeColors['600']).toBe('#F58300');
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
