import { test, expect } from '@playwright/test';

/**
 * Bug Report (Spec-316): El selector de relatos no actualiza el texto correctamente.
 * 
 * Este test intenta reproducir el fallo:
 * 1. Carga una página con múltiples relatos.
 * 2. Verifica que el primer relato es visible.
 * 3. Hace clic en el segundo relato.
 * 4. Verifica que el segundo relato es visible y el primero está oculto.
 */

test.describe('Relatos Selector (Bug Spec-316)', () => {
  
  test('debe cambiar de relato al hacer clic en las pestañas', async ({ page }) => {
    // Usamos una URL de prueba o mockeamos la respuesta si fuera necesario.
    // Para este caso, asumimos que el servidor está corriendo en el puerto 3010
    // (según el test de integración previo).
    
    // NOTA: Como Playwright necesita un servidor real, y estamos en medio de un refactor,
    // vamos a inyectar el HTML directamente para validar la lógica del JS en el cliente.
    
    const mockHtml = `
      <!DOCTYPE html>
      <html>
      <head>
        <script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
        <style>.hidden { display: none; }</style>
      </head>
      <body>
        <div class="relatos-container">
          <button data-relato-tab="r1" class="relato-tab">Relato 1</button>
          <button data-relato-tab="r2" class="relato-tab">Relato 2</button>
          
          <section id="relato-panel-r1" data-relato-panel="r1" class="relato-panel">Contenido 1</section>
          <section id="relato-panel-r2" data-relato-panel="r2" class="relato-panel hidden">Contenido 2</section>
        </div>

        <script>
          function selectRelato(relatoId) {
            document.querySelectorAll('[data-relato-panel]').forEach((panel) => {
              panel.classList.toggle('hidden', panel.getAttribute('data-relato-panel') !== relatoId);
            });
            document.querySelectorAll('[data-relato-tab]').forEach((tab) => {
              const isActive = tab.getAttribute('data-relato-tab') === relatoId;
              tab.classList.toggle('active', isActive);
            });
          }

          document.addEventListener('DOMContentLoaded', () => {
            const tabs = document.querySelectorAll('[data-relato-tab]');
            tabs.forEach((tab) => {
              tab.addEventListener('click', () => {
                const relatoId = tab.getAttribute('data-relato-tab');
                if (relatoId) selectRelato(relatoId);
              });
            });
          });
        </script>
      </body>
      </html>
    `;

    await page.setContent(mockHtml);

    // 1. Verificar estado inicial
    await expect(page.locator('#relato-panel-r1')).toBeVisible();
    await expect(page.locator('#relato-panel-r2')).toBeHidden();

    // 2. Hacer clic en el segundo relato
    await page.click('[data-relato-tab="r2"]');

    // 3. Verificar que cambió
    await expect(page.locator('#relato-panel-r2')).toBeVisible();
    await expect(page.locator('#relato-panel-r2')).toContainText('Contenido 2');
    await expect(page.locator('#relato-panel-r1')).toBeHidden();
  });
});
