/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/views/**/*.ejs',
    './src/public/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        forge: {
          bg:      'var(--forge-bg)',
          surface: 'var(--forge-surface)',
          border:  'var(--forge-border)',
          accent:  'var(--forge-accent)',
          muted:   'var(--forge-muted)',
          text:    'var(--forge-text)',
        },
        // Colores adicionales
        orange: {
          '600': '#F58300',  // RGB(245, 131, 0)
          'light': '#ffa500',
          'dark': '#cc6600',
        },
      },
      fontFamily: {
        serif: ['Georgia', 'serif'],
        mono:  ['"Courier New"', 'monospace'],
      },
      fontSize: {
        'xs': '0.85rem',
        'sm': '1rem',
        'base': '1.125rem',
        'lg': '1.25rem',
        'xl': '1.5rem',
        '2xl': '1.875rem',
        '3xl': '2.25rem',
      },
    },
  },
  plugins: [],
};
