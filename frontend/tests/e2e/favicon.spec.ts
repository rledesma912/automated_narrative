import { test, expect } from "@playwright/test";

// Spec-531 S4: los archivos del favicon se sirven con el tipo correcto.
const FILES: Array<[string, string]> = [
  ["/favicon.svg", "image/svg+xml"],
  ["/favicon-32.png", "image/png"],
  ["/apple-touch-icon.png", "image/png"],
];

for (const [url, type] of FILES) {
  test(`sirve ${url} como ${type}`, async ({ request }) => {
    const resp = await request.get(url);
    expect(resp.status()).toBe(200);
    expect(resp.headers()["content-type"]).toContain(type);
  });
}
