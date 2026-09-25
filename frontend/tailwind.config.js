/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/views/**/*.ejs',
    './src/public/**/*.html',
    // Clases que arman los scripts del cliente (sin esto, p.ej. el punto verde/rojo
    // del Core en el pie o los estados de la sala no existían en el CSS compilado).
    './public/js/**/*.js',
    './src/styles/**/*.css',
    // Clases armadas en TS (p. ej. el semáforo de las maquetas del asistente, Spec-530).
    './src/**/*.ts',
  ],
  safelist: [
    'btn-forge',
    'btn-forge-lg',
    'btn-forge-sm',
    'btn-forge-outline',
    'btn-forge-outline-sm',
    'btn-forge-danger',
  ],
  theme: {
    extend: {
      colors: {
        // Spec-531: la paleta vive en src/styles/theme.css. Con `color-mix` las
        // clases admiten opacidad (`bg-forge-accent/10`); con `var()` plano
        // Tailwind no generaba esas clases.
        forge: Object.fromEntries(
          [
            "bg", "surface", "border", "text", "muted", "accent", "on-accent",
            "error", "error-bg", "error-border",
            "warning", "warning-bg", "warning-border",
            "success", "success-bg", "success-border",
            "info", "info-bg", "info-border",
          ].map((name) => [
            name,
            `color-mix(in srgb, var(--forge-${name}) calc(<alpha-value> * 100%), transparent)`,
          ]).concat([["overlay", "var(--forge-overlay)"]]),
        ),
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
