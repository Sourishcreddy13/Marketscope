import { expect, test } from '@playwright/test'
import { ADMIN, adminToken, bearer, registerCustomer, signInViaUi } from './helpers'

test('AC-01 a new customer registers from the UI and lands on the overview', async ({ page }) => {
  const email = `ui-${Date.now().toString(36)}@example.com`
  await page.goto('/login')
  await page.getByRole('button', { name: 'Need an account? Register' }).click()
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill('Password@123')
  await page.getByRole('button', { name: 'Register' }).click()
  await expect(page.getByRole('heading', { name: /Welcome back/ })).toBeVisible()
  await expect(page.getByText('CUSTOMER', { exact: true })).toBeVisible()
})

test('a stale token is rejected on startup and the user is sent to sign-in', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('marketscope_token', 'not-a-valid-token'))
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
  await expect.poll(() => page.evaluate(() => localStorage.getItem('marketscope_token'))).toBeNull()
})

test('a revoked session recovers to sign-in with a notice instead of a stuck page', async ({ page, request }) => {
  const customer = await registerCustomer(request)
  await signInViaUi(page, customer.email, customer.password)
  const admin = await adminToken(request)
  const suspended = await request.patch(`/api/v1/admin/users/${customer.id}/role`, { headers: bearer(admin), data: { role: 'SUSPENDED' } })
  expect(suspended.status()).toBe(200)

  await page.getByRole('link', { name: 'Trade' }).click()
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
  await expect(page.getByRole('alert')).toContainText('session has expired')
})

test('wrong credentials show an error and do not trigger the session-expired flow', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Password').fill('Wrong@Password1')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('alert')).toContainText(/invalid credentials/i)
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
})

test('ADMIN can sign in and reach the operations console', async ({ page }) => {
  await signInViaUi(page, ADMIN.email, ADMIN.password)
  await page.getByRole('link', { name: 'Admin' }).click()
  await expect(page.getByRole('heading', { name: 'Operations control room' })).toBeVisible()
})
