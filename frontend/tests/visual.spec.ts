import { expect, test } from '@playwright/test'

// Visual-regression evidence: baselines live in tests/snapshots/ (regenerate with `npm run e2e -- --update-snapshots`).
test('login page matches the desktop snapshot', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
  await expect(page).toHaveScreenshot('login-desktop.png')
})

test('login page matches the mobile snapshot and does not scroll horizontally', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(0)
  await expect(page).toHaveScreenshot('login-mobile.png')
})
