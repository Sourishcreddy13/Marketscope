import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// E2E runs its own backend on another port (VITE_API_TARGET) so it never touches the dev server or dev database.
declare const process: { env: Record<string, string | undefined> }
const apiTarget = process.env.VITE_API_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': apiTarget,
      '/health': apiTarget,
    },
  },
  // Unit tests live beside the source; Playwright specs under tests/ are run by `npm run e2e`.
  test: { include: ['src/**/*.test.{ts,tsx}'], exclude: ['node_modules/**', 'tests/**', 'dist/**'] },
})
