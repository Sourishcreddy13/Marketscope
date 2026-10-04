import { expect, test } from '@playwright/test'
import { registerCustomer, signInViaUi } from './helpers'

async function openTrade(page: import('@playwright/test').Page, request: import('@playwright/test').APIRequestContext) {
  const customer = await registerCustomer(request)
  await signInViaUi(page, customer.email, customer.password)
  await page.getByRole('link', { name: 'Trade' }).click()
  await expect(page.getByRole('heading', { name: 'Order ticket' })).toBeVisible()
  await page.getByLabel('Symbol').selectOption({ label: 'AAPL — Apple Inc.' })
  return customer
}

test('AC-06/AC-07 customer places a market order and cancels it while PENDING', async ({ page, request }) => {
  await openTrade(page, request)
  await page.getByLabel('Quantity').fill('1.0000')
  await page.getByRole('button', { name: 'Place BUY order' }).click()
  await expect(page.getByText('Order accepted into PENDING state.')).toBeVisible()
  const row = page.locator('tbody tr', { hasText: 'AAPL' }).first()
  await expect(row.locator('.badge')).toHaveText('PENDING')

  await row.getByRole('button', { name: 'Cancel' }).click()
  await expect(page.locator('tbody tr', { hasText: 'AAPL' }).first().locator('.badge')).toHaveText('CANCELLED')
})

test('AC-06 a limit order requires and records its limit price', async ({ page, request }) => {
  await openTrade(page, request)
  await page.getByLabel('Type').selectOption('LIMIT')
  await page.getByLabel('Limit price').fill('100.0000')
  await page.getByRole('button', { name: 'Place BUY order' }).click()
  await expect(page.getByText('Order accepted into PENDING state.')).toBeVisible()
  await expect(page.locator('tbody tr', { hasText: 'LIMIT' }).first().locator('.badge')).toHaveText('PENDING')
})

test('AC-08 a BUY larger than available cash is refused', async ({ page, request }) => {
  await openTrade(page, request)
  await page.getByLabel('Quantity').fill('1000000')
  await page.getByRole('button', { name: 'Place BUY order' }).click()
  await expect(page.getByRole('alert')).toContainText(/exceeds available cash/i)
  await expect(page.locator('tbody tr')).toHaveCount(0)
})

test('a double click places exactly one order (button locks, one idempotency key)', async ({ page, request }) => {
  await openTrade(page, request)
  let posts = 0
  await page.route('**/api/v1/orders', async route => {
    if (route.request().method() === 'POST') {
      posts += 1
      await new Promise(resolve => setTimeout(resolve, 600)) // widen the in-flight window
    }
    await route.continue()
  })
  const button = page.getByRole('button', { name: 'Place BUY order' })
  await button.dblclick()
  await expect(page.getByText('Order accepted into PENDING state.')).toBeVisible()
  await expect(page.locator('tbody tr')).toHaveCount(1)
  expect(posts).toBe(1)
})

test('a retry after a lost response reuses the Idempotency-Key and still creates one order', async ({ page, request }) => {
  await openTrade(page, request)
  const keys: string[] = []
  await page.route('**/api/v1/orders', async route => {
    if (route.request().method() !== 'POST') return route.continue()
    keys.push(route.request().headers()['idempotency-key'])
    if (keys.length === 1) {
      await route.fetch() // the server accepts the order...
      await route.abort('failed') // ...but the client never sees the response
      return
    }
    await route.continue()
  })
  const button = page.getByRole('button', { name: 'Place BUY order' })
  await button.click()
  await expect(page.getByRole('alert')).toBeVisible()
  await button.click() // the user retries the same ticket
  await expect(page.getByText('Order accepted into PENDING state.')).toBeVisible()
  await expect(page.locator('tbody tr')).toHaveCount(1)
  expect(keys).toHaveLength(2)
  expect(keys[1]).toBe(keys[0])
  expect(keys[0].length).toBeGreaterThanOrEqual(8)

  // A different ticket is a different intent and gets a fresh key.
  await page.getByLabel('Quantity').fill('3.0000')
  await button.click()
  await expect(page.locator('tbody tr')).toHaveCount(2)
  expect(keys[2]).not.toBe(keys[0])
})

test('a second click after a successful order does not create another order', async ({ page, request }) => {
  await openTrade(page, request)
  await page.getByRole('button', { name: 'Place BUY order' }).click()
  await expect(page.getByText('Order accepted into PENDING state')).toBeVisible()
  const placed = page.getByRole('button', { name: 'Order placed' })
  await expect(placed).toBeDisabled()
  await placed.click({ force: true }).catch(() => undefined)
  await expect(page.locator('tbody tr')).toHaveCount(1)
  await page.getByLabel('Quantity').fill('2.0000') // editing the ticket re-arms it for a new, deliberate order
  await expect(page.getByRole('button', { name: 'Place BUY order' })).toBeEnabled()
})

test('an unreachable backend shows a clear message instead of a raw server error', async ({ page, request }) => {
  await openTrade(page, request)
  await page.route('**/api/v1/orders', route => route.abort('connectionrefused'))
  await page.getByRole('button', { name: 'Place BUY order' }).click()
  await expect(page.getByRole('alert')).toContainText('Cannot reach the server')
  await page.unroute('**/api/v1/orders')
  await page.route('**/api/v1/orders', route => route.request().method() === 'POST' ? route.fulfill({ status: 500, contentType: 'text/plain', body: 'Internal Server Error' }) : route.continue())
  await page.getByRole('button', { name: 'Place BUY order' }).click()
  await expect(page.getByRole('alert')).toContainText('server is unavailable')
})
