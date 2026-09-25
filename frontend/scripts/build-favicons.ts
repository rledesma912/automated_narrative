/**
 * Spec-531 S4: genera los PNG del favicon desde public/favicon.svg con el
 * Chromium de Playwright (ya está en el proyecto: sin dependencias nuevas).
 *
 *   npx ts-node scripts/build-favicons.ts
 *
 * - favicon-32.png: respaldo para navegadores sin favicon SVG.
 * - apple-touch-icon.png (180 px): iOS redondea las esquinas por su cuenta,
 *   así que el fondo va cuadrado.
 */
import fs from "fs";
import path from "path";
import { chromium } from "@playwright/test";

const PUBLIC = path.resolve(__dirname, "..", "public");
const svg = fs.readFileSync(path.join(PUBLIC, "favicon.svg"), "utf-8");

const TARGETS: Array<{ file: string; size: number; square: boolean }> = [
  { file: "favicon-32.png", size: 32, square: false },
  { file: "apple-touch-icon.png", size: 180, square: true },
];

async function main(): Promise<void> {
  const browser = await chromium.launch();
  try {
    for (const { file, size, square } of TARGETS) {
      const source = square ? svg.replace(' rx="7"', "") : svg;
      const page = await browser.newPage({ viewport: { width: size, height: size } });
      await page.setContent(
        `<html><body style="margin:0">${source.replace("<svg ", `<svg width="${size}" height="${size}" `)}</body></html>`,
      );
      await page.screenshot({ path: path.join(PUBLIC, file), omitBackground: true });
      await page.close();
      console.log(`${file} (${size}×${size})`);
    }
  } finally {
    await browser.close();
  }
}

main();
