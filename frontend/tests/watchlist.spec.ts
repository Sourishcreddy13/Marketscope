import { expect, test } from '@playwright/test'
import { registerCustomer, signInViaUi } from './helpers'

const pick = (page: import('@playwright/test').Page, symbol: string) => page.locator('label.check', { hasText: symbol }).click()

test('AC-04/AC-05 customer creates, edits atomically, and deletes a watchlist', async ({ page, request }) => {
  const customer = await registerCustomer(request)
  await signInViaUi(page, customer.email, customer.password)
  await page.getByRole('link', { name: 'Watchlists' }).click()
  await expect(page.getByRole('heading', { name: 'Curate your symbols' })).toBeVisible()

  // Create with one symbol.
  await page.getByLabel('Name', { exact: true }).fill('E2E Tech')
  await pick(page, 'AAPL')
  await page.getByRole('button', { name: 'Create watchlist' }).click()
  const card = page.locator('article.list-card', { hasText: 'E2E Tech' })
  await expect(card).toBeVisible()
  await expect(card.locator('.chip', { hasText: 'AAPL' })).toBeVisible()

  // Rename and add a symbol in one atomic save.
  await card.getByRole('button', { name: 'Edit' }).click()
  await page.getByLabel('Name', { exact: true }).fill('E2E Renamed')
  await pick(page, 'MSFT')
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.getByText('Watchlist updated atomically.')).toBeVisible()
  const renamed = page.locator('article.list-card', { hasText: 'E2E Renamed' })
  await expect(renamed.locator('.chip')).toHaveCount(2)

  // Remove a symbol.
  await renamed.getByRole('button', { name: 'Edit' }).click()
  await pick(page, 'AAPL')
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.locator('article.list-card', { hasText: 'E2E Renamed' }).locator('.chip')).toHaveCount(1)

  // Delete.
  await page.locator('article.list-card', { hasText: 'E2E Renamed' }).getByRole('button', { name: 'Delete' }).click()
  await expect(page.getByText('No watchlists yet.')).toBeVisible()
})

test('AC-04 a watchlist needs a name and at least one symbol', async ({ page, request }) => {
  const customer = await registerCustomer(request)
  await signInViaUi(page, customer.email, customer.password)
  await page.getByRole('link', { name: 'Watchlists' }).click()
  await page.getByRole('button', { name: 'Create watchlist' }).click()
  await expect(page.getByText('Name and at least one symbol are required.')).toBeVisible()
})
