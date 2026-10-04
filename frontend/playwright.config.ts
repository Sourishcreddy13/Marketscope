import { defineConfig, devices } from '@playwright/test'

// E2E runs against a dedicated, freshly migrated + seeded SQLite file so it never touches dev data.
const backendEnv = {
  ENVIRONMENT: 'test',
  DATABASE_URL: 'sqlite:///./data/e2e.db',
  AUTH_RATE_LIMIT_ATTEMPTS: '1000',
  MARKET_TICK_INTERVAL_SECONDS: '3600',
}

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  expect: { toHaveScreenshot: { maxDiffPixelRatio: 0.03 } },
  snapshotPathTemplate: '{testDir}/snapshots/{testFilePath}/{arg}{ext}',
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: 'http://127.0.0.1:5174',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    // Optional: point at a locally installed Chromium instead of Playwright's managed build.
    launchOptions: { executablePath: process.env.PW_CHROMIUM_EXECUTABLE || undefined },
  },
  webServer: [
    {
      command: 'cd .. && rm -f data/e2e.db && uv run alembic upgrade head && uv run python -m scripts.seed_data && uv run uvicorn app.main:app --host 127.0.0.1 --port 8100',
      url: 'http://127.0.0.1:8100/health',
      env: backendEnv,
      reuseExistingServer: false, // never reuse a dev server: it has other settings and the dev database
      timeout: 120_000,
      stdout: 'ignore',
    },
    {
      command: 'npx vite --config vite.config.ts --host 127.0.0.1 --port 5174 --strictPort',
      url: 'http://127.0.0.1:5174',
      env: { VITE_API_TARGET: 'http://127.0.0.1:8100' },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  reporter: [['list'], ['html', { open: 'never' }]],
})
