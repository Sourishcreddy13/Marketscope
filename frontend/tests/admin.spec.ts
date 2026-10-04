import { expect, test } from '@playwright/test'
import { ADMIN, adminToken, bearer, orderStatus, placeOrderViaApi, registerCustomer, signInViaUi, stockIdFor } from './helpers'

async function openAdmin(page: import('@playwright/test').Page) {
  await signInViaUi(page, ADMIN.email, ADMIN.password)
  await page.getByRole('link', { name: 'Admin' }).click()
  await expect(page.getByRole('heading', { name: 'Operations control room' })).toBeVisible()
}

test('AC-03 ADMIN creates, edits, and soft-deletes a stock (never hard-deleted)', async ({ page, request }) => {
  const symbol = `E${Date.now().toString(36).toUpperCase().slice(-6)}`
  await openAdmin(page)

  const create = page.locator('section', { hasText: 'Create stock' }).first()
  await create.getByLabel('Symbol').fill(symbol)
  await create.getByLabel('Name').fill('E2E Corp')
  await create.getByLabel('Sector').fill('Testing')
  await create.getByRole('button', { name: 'Create stock' }).click()
  const row = page.locator('tbody tr', { hasText: symbol })
  await expect(row).toContainText('E2E Corp')
  await expect(row.locator('.badge')).toHaveText('ACTIVE')

  await row.getByRole('button', { name: 'Edit' }).click()
  await page.getByLabel(`Name for ${symbol}`).fill('E2E Corp Renamed')
  await page.getByLabel(`Sector for ${symbol}`).fill('Updated Sector')
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByText('Stock updated.')).toBeVisible()
  await expect(page.locator('tbody tr', { hasText: symbol })).toContainText('E2E Corp Renamed')
  await expect(page.locator('tbody tr', { hasText: symbol })).toContainText('Updated Sector')

  await page.locator('tbody tr', { hasText: symbol }).getByRole('button', { name: 'Soft-delete' }).click()
  await expect(page.locator('tbody tr', { hasText: symbol }).locator('.badge')).toHaveText('DELETED')

  const token = await adminToken(request)
  const rows: Array<{ symbol: string; status: string }> = await (await request.get('/api/v1/admin/stocks', { headers: bearer(token) })).json()
  expect(rows.find(r => r.symbol === symbol)?.status).toBe('DELETED')
})

test('AC-03 blank stock fields are refused by the console', async ({ page }) => {
  await openAdmin(page)
  const create = page.locator('section', { hasText: 'Create stock' }).first()
  await create.getByLabel('Symbol').fill('   ')
  await create.getByLabel('Name').fill('Blank Corp')
  await create.getByLabel('Sector').fill('Testing')
  await create.getByRole('button', { name: 'Create stock' }).click()
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page.locator('tbody tr', { hasText: 'Blank Corp' })).toHaveCount(0)
})

test('AC-07 ADMIN executes and rejects pending orders; most-traded shows the symbol', async ({ page, request, browser, baseURL }) => {
  const customer = await registerCustomer(request)
  const aapl = await stockIdFor(request, customer.token, 'AAPL')
  const toExecute = await placeOrderViaApi(request, customer.token, aapl, '1.0000')
  const toReject = await placeOrderViaApi(request, customer.token, aapl, '1.0000')

  await openAdmin(page)
  await page.locator('tbody tr', { hasText: toExecute.id.slice(0, 8) }).getByRole('button', { name: 'Execute' }).click()
  await expect(page.locator('tbody tr', { hasText: toExecute.id.slice(0, 8) })).toHaveCount(0)
  const rejectRow = page.locator('tbody tr', { hasText: toReject.id.slice(0, 8) })
  await rejectRow.getByRole('button', { name: 'Reject' }).click()
  await rejectRow.getByRole('button', { name: 'Confirm reject' }).click() // a reason is mandatory
  await expect(page.getByRole('alert')).toContainText('reason')
  await rejectRow.getByLabel('Rejection reason').fill('Position limit exceeded')
  await rejectRow.getByRole('button', { name: 'Confirm reject' }).click()
  await expect(page.locator('tbody tr', { hasText: toReject.id.slice(0, 8) })).toHaveCount(0)

  const token = await adminToken(request)
  expect(await orderStatus(request, token, toExecute.id)).toBe('EXECUTED')
  expect(await orderStatus(request, token, toReject.id)).toBe('REJECTED')

  // The customer sees why on their own order history.
  // A separate browser context: the admin's session must not leak into the customer's.
  const customerContext = await browser.newContext({ baseURL })
  const customerPage = await customerContext.newPage()
  await signInViaUi(customerPage, customer.email, customer.password)
  await customerPage.getByRole('link', { name: 'Trade' }).click()
  await expect(customerPage.getByText('Reason: Position limit exceeded')).toBeVisible()
  await customerContext.close()

  const mostTraded = page.locator('section', { hasText: 'Most-traded symbols' }).last()
  await expect(mostTraded.getByText('AAPL', { exact: true })).toBeVisible()
})

test('AC-02 ADMIN suspends a customer, who can then no longer sign in', async ({ page, request, browser, baseURL }) => {
  const customer = await registerCustomer(request)
  await openAdmin(page)
  await page.getByLabel(`Role for ${customer.email}`).selectOption('SUSPENDED')
  await expect(page.locator('tbody tr', { hasText: customer.email }).locator('.badge')).toHaveText('SUSPENDED')

  const login = await request.post('/api/v1/auth/login', { data: { email: customer.email, password: customer.password } })
  expect(login.status()).toBe(403)
  const wrong = await request.post('/api/v1/auth/login', { data: { email: customer.email, password: 'Wrong@Password1' } })
  expect(wrong.status()).toBe(401) // suspension is only revealed to the account owner

  // The sign-in page tells the owner what happened instead of "invalid credentials".
  const otherContext = await browser.newContext({ baseURL })
  const other = await otherContext.newPage()
  await other.goto('/login')
  await other.getByLabel('Email').fill(customer.email)
  await other.getByLabel('Password').fill(customer.password)
  await other.getByRole('button', { name: 'Sign in' }).click()
  await expect(other.getByRole('alert')).toContainText('suspended')
  await otherContext.close()
})

test('AC-03 blank stock fields show a clear message beside the form and create nothing', async ({ page }) => {
  await openAdmin(page)
  const panel = page.locator('section', { hasText: 'Create stock' }).first()
  await panel.getByRole('button', { name: 'Create stock' }).click()
  await expect(panel.getByRole('alert')).toContainText('Please fill in')
  await panel.getByLabel('Symbol').fill('   ')
  await panel.getByLabel('Name').fill('Spaces Only Inc')
  await panel.getByLabel('Sector').fill('Tech')
  await panel.getByRole('button', { name: 'Create stock' }).click()
  await expect(panel.getByRole('alert')).toContainText('symbol')
})

test('NFR-04 a CUSTOMER cannot use the admin console or admin API', async ({ page, request }) => {
  const customer = await registerCustomer(request)
  await signInViaUi(page, customer.email, customer.password)
  await page.goto('/admin')
  await expect(page.getByRole('heading', { name: 'Access denied' })).toBeVisible()
  const response = await request.get('/api/v1/admin/users', { headers: bearer(customer.token) })
  expect(response.status()).toBe(403)
})
