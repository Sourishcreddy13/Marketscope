import { expect, test } from '@playwright/test'
import { adminToken, bearer, placeOrderViaApi, registerCustomer, signInViaUi, stockIdFor } from './helpers'

test('AC-09/AC-10 customer sees executed holdings, fixed-point P&L, and analytics', async ({ page, request }) => {
  const customer = await registerCustomer(request)
  const admin = await adminToken(request)
  const aapl = await stockIdFor(request, customer.token, 'AAPL')
  const order = await placeOrderViaApi(request, customer.token, aapl, '2.0000')
  const executed = await request.post(`/api/v1/admin/orders/${order.id}/execute`, { headers: bearer(admin) })
  expect(executed.status()).toBe(200)

  await signInViaUi(page, customer.email, customer.password)
  const holding = page.locator('tbody tr', { hasText: 'AAPL' }).first()
  await expect(holding).toContainText('2.0000')
  await expect(page.getByText('Absolute P&L')).toBeVisible()
  await expect(page.getByText('P&L %')).toBeVisible()
  // Cash left after buying 2 x AAPL at the accepted quote; currency strings come straight from decimal text.
  await expect(page.getByText(/₹\d{1,3}(,\d{3})*\.\d{2}/).first()).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Daily movers' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Sector exposure' })).toBeVisible()
  await expect(page.getByText('Technology')).toBeVisible()

  const stats = await (await request.get('/api/v1/portfolio', { headers: bearer(customer.token) })).json()
  expect(stats.holdings).toHaveLength(1)
  expect(stats.total_invested).toMatch(/^\d+\.\d{4}$/)
})

test('an optional analytics failure does not blank the dashboard', async ({ page, request }) => {
  const customer = await registerCustomer(request)
  await page.route('**/api/v1/portfolio/daily-stats', route => route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"boom"}' }))
  await signInViaUi(page, customer.email, customer.password)
  await expect(page.getByText('Available cash')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Current holdings' })).toBeVisible()
  await expect(page.getByRole('alert').filter({ hasText: 'boom' })).toBeVisible()
})
