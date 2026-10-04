export type User = { id: string; email: string; role: 'CUSTOMER' | 'ADMIN' | 'SUSPENDED'; created_at: string }
export type Stock = { id: string; symbol: string; name: string; sector: string; exchange: string; status: 'ACTIVE'|'DELETED'; created_at: string; updated_at: string }
export type Quote = { stock_id: string; symbol: string; price: string; occurred_at: string | null; previous_price: string | null; change_percent: string | null }
export type Holding = { stock_id: string; symbol: string; quantity: string; average_buy_price: string; current_price: string; current_value: string; invested_value: string; absolute_pnl: string; percent_pnl: string }
export type Portfolio = { total_invested: string; current_value: string; absolute_pnl: string; percent_pnl: string; available_cash: string; holdings: Holding[] }
export type Watchlist = { id: string; name: string; stock_ids: string[]; created_at: string; updated_at: string }
export type Order = { id: string; customer_id: string; stock_id: string; side: 'BUY'|'SELL'; order_type: 'MARKET'|'LIMIT'; quantity: string; limit_price: string|null; quote_price: string; status: 'PENDING'|'EXECUTED'|'CANCELLED'|'REJECTED'; created_at: string; executed_at: string|null; cancelled_at: string|null; rejected_at: string|null; rejection_reason: string|null }
export type DailyStat = { stock_id: string; symbol: string; percent_pnl: string; absolute_pnl: string }
export type DailyStats = { top_5_gainers: DailyStat[]; top_5_losers: DailyStat[] }
export type SectorExposure = { sector: string; value: string; percent: string }
export type MostTraded = { stock_id: string; symbol: string; executed_order_count: number }
export type OrderStats = { total_orders: number; by_status: Record<string, number>; settlement_queue: { pending_orders: number }; most_traded_stocks: MostTraded[] }

const TOKEN_KEY = 'marketscope_token'

export function getToken(): string | null { return localStorage.getItem(TOKEN_KEY) }
export function setToken(token: string): void { localStorage.setItem(TOKEN_KEY, token) }
export function clearToken(): void { localStorage.removeItem(TOKEN_KEY) }

// Centralized session invalidation: any 401 on a protected endpoint clears the token and notifies
// the session provider, which sends the user back to the sign-in page.
const CREDENTIAL_PATHS = new Set(['/api/v1/auth/login', '/api/v1/auth/register'])
const expiryListeners = new Set<() => void>()
export function onSessionExpired(listener: () => void): () => void {
  expiryListeners.add(listener)
  return () => { expiryListeners.delete(listener) }
}

// FastAPI returns `detail` as a string for domain errors and as a list of {loc, msg} for field validation errors.
function describeDetail(detail: unknown): string | null {
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length) {
    return detail.map(item => {
      const entry = item as { loc?: unknown[]; msg?: string }
      const field = Array.isArray(entry.loc) ? String(entry.loc[entry.loc.length - 1]) : ''
      const msg = (entry.msg ?? 'is invalid').replace(/^Value error, /, '')
      return field && field !== 'body' ? `${field}: ${msg}` : msg
    }).join('; ')
  }
  return null
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  let response: Response
  try {
    response = await fetch(path, { ...init, headers })
  } catch {
    throw new Error('Cannot reach the server. Check your connection and that the backend is running, then try again.')
  }
  const requestId = response.headers.get('X-Request-ID')
  if (response.status === 401 && !CREDENTIAL_PATHS.has(path)) {
    clearToken()
    expiryListeners.forEach(listener => listener())
    throw new Error('Your session has expired. Please sign in again.')
  }
  if (!response.ok) {
    // A stopped backend behind the dev proxy answers with a bare 5xx that is not JSON.
    const unavailable = 'The server is unavailable right now. Please try again in a moment.'
    const body = await response.json().catch(() => ({ detail: response.status >= 500 ? unavailable : response.statusText })) as { detail?: unknown }
    const message = describeDetail(body.detail) ?? (response.status >= 500 ? unavailable : `Request failed (${response.status})`)
    throw new Error(requestId ? `${message} [${requestId.slice(0, 8)}]` : message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export function login(email: string, password: string) { return request<{ access_token: string; user: User }>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }) }
export function register(email: string, password: string) { return request<{ access_token: string; user: User }>('/api/v1/auth/register', { method: 'POST', body: JSON.stringify({ email, password }) }) }
export function me() { return request<User>('/api/v1/auth/me') }
export function updateProfile(payload: { email?: string; current_password?: string; new_password?: string }) { return request<User>('/api/v1/auth/me', { method: 'PATCH', body: JSON.stringify(payload) }) }
export function closeAccount(currentPassword: string) { return request<User>('/api/v1/auth/me', { method: 'DELETE', body: JSON.stringify({ current_password: currentPassword }) }) }
export function stocks(q = '') { return request<Stock[]>(`/api/v1/stocks${q ? `?q=${encodeURIComponent(q)}` : ''}`) }
export function adminStocks() { return request<Stock[]>('/api/v1/admin/stocks') }
export function createStock(payload: { symbol: string; name: string; sector: string; exchange: string }) { return request<Stock>('/api/v1/admin/stocks', { method: 'POST', body: JSON.stringify(payload) }) }
export function updateStock(id: string, payload: Partial<{ name: string; sector: string; exchange: string }>) { return request<Stock>(`/api/v1/admin/stocks/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }) }
export function deleteStock(id: string) { return request<Stock>(`/api/v1/admin/stocks/${id}`, { method: 'DELETE' }) }
export function users() { return request<User[]>('/api/v1/admin/users') }
export function updateRole(id: string, role: User['role']) { return request<User>(`/api/v1/admin/users/${id}/role`, { method: 'PATCH', body: JSON.stringify({ role }) }) }
export function portfolio() { return request<Portfolio>('/api/v1/portfolio') }
export function dailyStats() { return request<DailyStats>('/api/v1/portfolio/daily-stats') }
export function sectorExposure() { return request<SectorExposure[]>('/api/v1/portfolio/sector-exposure') }
export function quotes() { return request<Quote[]>('/api/v1/market-data') }
export function watchlists() { return request<Watchlist[]>('/api/v1/watchlists') }
export function createWatchlist(payload: { name: string; stock_ids: string[] }) { return request<Watchlist>('/api/v1/watchlists', { method: 'POST', body: JSON.stringify(payload) }) }
export function updateWatchlist(id: string, payload: { name?: string; stock_ids?: string[] }) { return request<Watchlist>(`/api/v1/watchlists/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }) }
export function deleteWatchlist(id: string) { return request<void>(`/api/v1/watchlists/${id}`, { method: 'DELETE' }) }
export function orders() { return request<Order[]>('/api/v1/orders') }
export function adminOrders() { return request<Order[]>('/api/v1/admin/orders') }
export function createOrder(payload: { stock_id: string; side: 'BUY'|'SELL'; order_type: 'MARKET'|'LIMIT'; quantity: string; limit_price?: string }, idempotencyKey: string) { return request<Order>('/api/v1/orders', { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey }, body: JSON.stringify(payload) }) }
export function cancelOrder(id: string) { return request<Order>(`/api/v1/orders/${id}/cancel`, { method: 'POST' }) }
export function executeOrder(id: string) { return request<Order>(`/api/v1/admin/orders/${id}/execute`, { method: 'POST' }) }
export function rejectOrder(id: string, reason: string) { return request<Order>(`/api/v1/admin/orders/${id}/reject?reason=${encodeURIComponent(reason)}`, { method: 'POST' }) }
export function orderStats() { return request<OrderStats>('/api/v1/admin/orders/stats') }
export function tickMarket() { return request<{ updated_symbols: number; prices: Record<string, string> }>('/api/v1/admin/market-data/tick', { method: 'POST' }) }
