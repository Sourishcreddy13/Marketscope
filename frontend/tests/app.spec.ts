import { expect, test } from '@playwright/test'
import { SEED_CUSTOMER, signInViaUi } from './helpers'

test('customer can sign in and reach portfolio overview', async ({ page }) => {
  await signInViaUi(page, SEED_CUSTOMER.email, SEED_CUSTOMER.password)
  await expect(page.getByText('Available cash')).toBeVisible()
})

test('customer can navigate to trade and watchlists', async ({ page }) => {
  await signInViaUi(page, SEED_CUSTOMER.email, SEED_CUSTOMER.password)
  await page.getByRole('link', { name: 'Trade' }).click()
  await expect(page.getByRole('heading', { name: 'Order ticket' })).toBeVisible()
  await page.getByRole('link', { name: 'Watchlists' }).click()
  await expect(page.getByRole('heading', { name: 'Curate your symbols' })).toBeVisible()
})
