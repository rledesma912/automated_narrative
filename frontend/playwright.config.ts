import os from "os";
import path from "path";
import { defineConfig, devices } from "@playwright/test";

/**
 * Por defecto Playwright levanta su propio entorno (Spec-460 S4):
 *   - Core en :8021 con DB descartable sembrada desde data/dev/stories.db y
 *     LLM mock con demora (tests/e2e_support/run_api_mock.py);
 *   - frontend en :3021 apuntando a ese Core.
 * Así los E2E no dependen de lo que esté corriendo en la máquina.
 *
 * Con BASE_URL definido se usa ese frontend y no se levanta nada.
 */
const API_PORT = 8021;
const UI_PORT = 3021;
const REPO_ROOT = path.resolve(__dirname, "..");
const useHarness = !process.env.BASE_URL;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: process.env.BASE_URL || `http://127.0.0.1:${UI_PORT}`,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: useHarness
    ? [
        {
          command: "uv run python tests/e2e_support/run_api_mock.py",
          cwd: REPO_ROOT,
          url: `http://127.0.0.1:${API_PORT}/api/v1/health`,
          reuseExistingServer: false,
          timeout: 60 * 1000,
          env: {
            E2E_DB: path.join(os.tmpdir(), "narrativeforge-e2e.db"),
            E2E_SEED_DB: path.join(REPO_ROOT, "data", "dev", "stories.db"),
            E2E_LLM_DELAY: "0.15",
            E2E_API_PORT: String(API_PORT),
            PYTHONPATH: REPO_ROOT,
          },
        },
        {
          command: "npm run build:css && npx ts-node src/server.ts",
          url: `http://127.0.0.1:${UI_PORT}/`,
          reuseExistingServer: false,
          timeout: 60 * 1000,
          env: {
            CORE_API_URL: `http://127.0.0.1:${API_PORT}`,
            PORT: String(UI_PORT),
          },
        },
      ]
    : undefined,
});
