import { expect, test } from '@playwright/test'
import { SEED_CUSTOMER, signInViaUi } from './helpers'

test.describe('catalog', () => {
  test.beforeEach(async ({ page }) => {
    await signInViaUi(page, SEED_CUSTOMER.email, SEED_CUSTOMER.password)
  })

  test('customer can search and filter the catalog', async ({ page }) => {
    await page.getByRole('link', { name: 'Catalog' }).click()
    await expect(page.getByRole('heading', { name: 'Explore the market universe' })).toBeVisible()
    await page.getByLabel('Search stocks').fill('Technology')
    await page.getByRole('button', { name: 'Search' }).click()
    await expect(page.getByText('AAPL', { exact: true })).toBeVisible()
    await expect(page.getByText('MSFT', { exact: true })).toBeVisible()
  })

  test('the catalog polls the REST market feed on a timer', async ({ page }) => {
    let quoteRequests = 0
    await page.route('**/api/v1/market-data', async route => { quoteRequests += 1; await route.continue() })
    await page.clock.install()
    await page.getByRole('link', { name: 'Catalog' }).click()
    await expect(page.getByRole('heading', { name: 'Explore the market universe' })).toBeVisible()
    const initial = quoteRequests
    await page.clock.fastForward(16_000)
    await expect.poll(() => quoteRequests).toBeGreaterThan(initial)
  })

  test('filters by exchange and price move, and sorts by price', async ({ page, request }) => {
    await page.getByRole('link', { name: 'Catalog' }).click()
    await page.getByLabel('Exchange').selectOption('NYSE')
    await expect(page.getByText('JPM', { exact: true })).toBeVisible()
    await expect(page.getByText('AAPL', { exact: true })).toHaveCount(0)
    await page.getByLabel('Exchange').selectOption('ALL')
    await page.getByLabel('Sort by').selectOption('PRICE_DESC')
    const symbols = await page.locator('.catalog-symbol').allTextContents()
    expect(symbols[0]).toBe('TSLA') // seeded prices: TSLA 440 is the highest
    await page.getByLabel('Price move').selectOption('UP')
    await expect(page.getByText(/active symbols/)).toBeVisible()
  })
})
