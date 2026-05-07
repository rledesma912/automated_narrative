import { describe, it, expect } from 'vitest';
import themes from '../../../config/themes.json';

interface ThemeDef {
  name: string;
  bg: string;
  surface: string;
  border: string;
  accent: string;
  muted: string;
  text: string;
  error?: string;
  'error-bg'?: string;
  'error-border'?: string;
  font: string;
}

/**
 * Spec-318: Tests Unitarios — Theme CSS Variables
 * 
 * Verifica que todos los themes tengan las variables de error centralizadas.
 */
describe('Theme CSS Variables — Error States', () => {
  it('horror theme tiene error vars', () => {
    const theme = themes['horror'] as ThemeDef;
    expect(theme.error).toBeDefined();
    expect(theme['error-bg']).toBeDefined();
    expect(theme['error-border']).toBeDefined();
  });

  it('noir theme tiene error vars', () => {
    const theme = themes['noir'] as ThemeDef;
    expect(theme.error).toBeDefined();
    expect(theme['error-bg']).toBeDefined();
    expect(theme['error-border']).toBeDefined();
  });

  it('light-contrast theme tiene error vars', () => {
    const theme = themes['light-contrast'] as ThemeDef;
    expect(theme.error).toBeDefined();
    expect(theme['error-bg']).toBeDefined();
    expect(theme['error-border']).toBeDefined();
  });

  it('todos los themes tienen las 3 variables de error', () => {
    const keys = ['horror', 'noir', 'light-contrast'];
    
    keys.forEach((key) => {
      const theme = themes[key] as ThemeDef;
      expect(theme.error, `${key}: error`).toBeDefined();
      expect(theme['error-bg'], `${key}: error-bg`).toBeDefined();
      expect(theme['error-border'], `${key}: error-border`).toBeDefined();
    });
  });
});

describe('Theme CSS Variables — Backward Compatibility', () => {
  it('todos los themes tienen las variables base', () => {
    const keys = ['horror', 'noir', 'light-contrast'];
    
    keys.forEach((key) => {
      const theme = themes[key] as ThemeDef;
      expect(theme.bg).toBeDefined();
      expect(theme.surface).toBeDefined();
      expect(theme.border).toBeDefined();
      expect(theme.accent).toBeDefined();
      expect(theme.muted).toBeDefined();
      expect(theme.text).toBeDefined();
    });
  });
});