import { expect, type APIRequestContext, type Page } from '@playwright/test'

export const ADMIN = { email: 'admin@marketscope.local', password: 'Admin@12345' }
export const SEED_CUSTOMER = { email: 'customer@marketscope.local', password: 'Customer@12345' }

export type Customer = { email: string; password: string; token: string; id: string }

let counter = 0
const unique = () => `${Date.now().toString(36)}${(counter += 1)}${Math.random().toString(36).slice(2, 6)}`

export const bearer = (token: string, extra: Record<string, string> = {}) => ({ Authorization: `Bearer ${token}`, ...extra })

/** Each test registers its own customer so state never leaks between tests. */
export async function registerCustomer(request: APIRequestContext): Promise<Customer> {
  const email = `e2e-${unique()}@example.com`
  const password = 'E2e@Password1'
  const response = await request.post('/api/v1/auth/register', { data: { email, password } })
  expect(response.status()).toBe(201)
  const body = await response.json()
  return { email, password, token: body.access_token, id: body.user.id }
}

export async function loginToken(request: APIRequestContext, email: string, password: string): Promise<string> {
  const response = await request.post('/api/v1/auth/login', { data: { email, password } })
  expect(response.status()).toBe(200)
  return (await response.json()).access_token
}

export const adminToken = (request: APIRequestContext) => loginToken(request, ADMIN.email, ADMIN.password)

export async function stockIdFor(request: APIRequestContext, token: string, symbol: string): Promise<string> {
  const rows: Array<{ id: string; symbol: string }> = await (await request.get('/api/v1/stocks', { headers: bearer(token) })).json()
  const row = rows.find(r => r.symbol === symbol)
  expect(row, `seed stock ${symbol}`).toBeTruthy()
  return row!.id
}

export async function placeOrderViaApi(request: APIRequestContext, token: string, stockId: string, quantity = '2.0000') {
  const response = await request.post('/api/v1/orders', {
    headers: bearer(token, { 'Idempotency-Key': `e2e-${unique()}` }),
    data: { stock_id: stockId, side: 'BUY', order_type: 'MARKET', quantity },
  })
  expect(response.status()).toBe(201)
  return (await response.json()) as { id: string; status: string }
}

export async function signInViaUi(page: Page, email: string, password: string) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: /Welcome back|Operations control room/ }).first()).toBeVisible()
}

export async function orderStatus(request: APIRequestContext, token: string, orderId: string): Promise<string> {
  const rows: Array<{ id: string; status: string }> = await (await request.get('/api/v1/admin/orders', { headers: bearer(token) })).json()
  return rows.find(r => r.id === orderId)?.status ?? 'MISSING'
}
