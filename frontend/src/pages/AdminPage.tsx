import { useCallback, useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { adminOrders, adminStocks, createStock, deleteStock, executeOrder, orderStats, rejectOrder, tickMarket, updateRole, updateStock, users, type Order, type OrderStats, type Stock, type User } from '../lib/api'
import { formatMoney } from '../lib/format'
import { useRequiredUser } from '../lib/session'

type StockDraft = { name: string; sector: string; exchange: string }
const errorText = (e: unknown, fallback: string) => (e instanceof Error ? e.message : fallback)

export default function AdminPage() {
  const user = useRequiredUser()
  const [userRows, setUserRows] = useState<User[]>([])
  const [stockRows, setStockRows] = useState<Stock[]>([])
  const [orderRows, setOrderRows] = useState<Order[]>([])
  const [stats, setStats] = useState<OrderStats | null>(null)
  const [form, setForm] = useState({ symbol: '', name: '', sector: '', exchange: 'NASDAQ' })
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState<StockDraft>({ name: '', sector: '', exchange: '' })
  const [rejectingId, setRejectingId] = useState<string | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const [createError, setCreateError] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const isAdmin = user.role === 'ADMIN'

  // Each section loads independently so one failing endpoint does not blank the console.
  const refresh = useCallback(async () => {
    const [ur, sr, os, st] = await Promise.allSettled([users(), adminStocks(), adminOrders(), orderStats()])
    if (ur.status === 'fulfilled') setUserRows(ur.value)
    if (sr.status === 'fulfilled') setStockRows(sr.value)
    if (os.status === 'fulfilled') setOrderRows(os.value)
    if (st.status === 'fulfilled') setStats(st.value)
    const failed = [ur, sr, os, st].find(result => result.status === 'rejected')
    if (failed && failed.status === 'rejected') setError(errorText(failed.reason, 'Some admin data could not be loaded'))
  }, [])
  useEffect(() => { if (isAdmin) refresh() }, [isAdmin, refresh])

  async function act(action: () => Promise<unknown>, success: string, failure: string) {
    setError(''); setMessage('')
    try { await action(); if (success) setMessage(success); await refresh() } catch (e) { setError(errorText(e, failure)) }
  }
  async function addStock() {
    setCreateError(''); setError(''); setMessage('')
    const blank = (['symbol', 'name', 'sector', 'exchange'] as const).filter(field => !form[field].trim())
    if (blank.length) { setCreateError(`Please fill in: ${blank.join(', ')}. Blank or space-only values are not allowed.`); return }
    try {
      await createStock({ symbol: form.symbol.trim(), name: form.name.trim(), sector: form.sector.trim(), exchange: form.exchange.trim() })
      setForm({ symbol: '', name: '', sector: '', exchange: 'NASDAQ' })
      setMessage('Stock created.')
      await refresh()
    } catch (e) { setCreateError(errorText(e, 'Stock creation failed')) }
  }
  const changeRole = (id: string, role: User['role']) => act(() => updateRole(id, role), '', 'Role update failed')
  const softDelete = (id: string) => act(() => deleteStock(id), 'Stock soft-deleted.', 'Delete failed')
  const execute = (id: string) => act(() => executeOrder(id), '', 'Execution failed')
  const reject = (id: string) => {
    const reason = rejectReason.trim()
    if (!reason) { setError('Enter a reason for rejecting the order; the customer will see it.'); return }
    return act(async () => { await rejectOrder(id, reason); setRejectingId(null); setRejectReason('') }, 'Order rejected.', 'Rejection failed')
  }
  const tick = () => act(async () => { const result = await tickMarket(); setMessage(`${result.updated_symbols} market prices updated.`) }, '', 'Market tick failed')

  function beginEdit(stock: Stock) { setEditingId(stock.id); setDraft({ name: stock.name, sector: stock.sector, exchange: stock.exchange }) }
  const saveEdit = () => editingId && act(async () => { await updateStock(editingId, draft); setEditingId(null) }, 'Stock updated.', 'Stock update failed')

  if (!isAdmin) return <Layout email={user.email} role={user.role}><div className="hero"><h1>Access denied</h1></div></Layout>
  return <Layout email={user.email} role={user.role}>
    <section className="hero"><div><span className="eyebrow">ADMIN CONSOLE</span><h1>Operations control room</h1><p className="muted">User administration, catalog control, order queue and synthetic market ticks.</p></div><button className="primary" onClick={tick}>Run market tick</button></section>
    {message && <div className="alert page-alert" role="status">{message}</div>}{error && <div className="alert error page-alert" role="alert">{error}</div>}
    <div className="metric-grid metric-grid-4"><Metric label="Orders" value={String(stats?.total_orders ?? 0)} /><Metric label="Pending" value={String(stats?.settlement_queue.pending_orders ?? 0)} /><Metric label="Executed" value={String(stats?.by_status.EXECUTED ?? 0)} /><Metric label="Rejected" value={String(stats?.by_status.REJECTED ?? 0)} /></div>
    <div className="grid-two">
      <section className="panel"><div className="panel-head"><h2>Create stock</h2><span className="muted">Soft-delete only</span></div><div className="form-grid"><label>Symbol<input value={form.symbol} onChange={e => setForm({ ...form, symbol: e.target.value })} /></label><label>Name<input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></label><label>Sector<input value={form.sector} onChange={e => setForm({ ...form, sector: e.target.value })} /></label><label>Exchange<input value={form.exchange} onChange={e => setForm({ ...form, exchange: e.target.value })} /></label></div>{createError && <div className="alert error top-gap" role="alert">{createError}</div>}<button className="primary top-gap" onClick={addStock}>Create stock</button></section>
      <section className="panel"><div className="panel-head"><h2>User roles</h2><span className="muted">Audited changes</span></div><div className="table-wrap"><table><thead><tr><th>Email</th><th>Role</th><th>Action</th></tr></thead><tbody>{userRows.map(row => <tr key={row.id}><td>{row.email}</td><td><span className="badge">{row.role}</span></td><td><select aria-label={`Role for ${row.email}`} value={row.role} onChange={e => changeRole(row.id, e.target.value as User['role'])}><option value="CUSTOMER">CUSTOMER</option><option value="ADMIN">ADMIN</option><option value="SUSPENDED">SUSPENDED</option></select></td></tr>)}</tbody></table></div></section>
    </div>
    <section className="panel page-section"><div className="panel-head"><h2>Stock catalog</h2><span className="muted">ADMIN CRUD with logical deletion</span></div><div className="table-wrap"><table><thead><tr><th>Symbol</th><th>Name</th><th>Sector</th><th>Exchange</th><th>Status</th><th>Action</th></tr></thead><tbody>{stockRows.map(stock => editingId === stock.id
      ? <tr key={stock.id}><td><strong>{stock.symbol}</strong></td><td><input aria-label={`Name for ${stock.symbol}`} value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} /></td><td><input aria-label={`Sector for ${stock.symbol}`} value={draft.sector} onChange={e => setDraft({ ...draft, sector: e.target.value })} /></td><td><input aria-label={`Exchange for ${stock.symbol}`} value={draft.exchange} onChange={e => setDraft({ ...draft, exchange: e.target.value })} /></td><td><span className="badge">{stock.status}</span></td><td><button className="small-button" onClick={saveEdit}>Save</button><button className="small-button" onClick={() => setEditingId(null)}>Cancel</button></td></tr>
      : <tr key={stock.id}><td><strong>{stock.symbol}</strong></td><td>{stock.name}</td><td>{stock.sector}</td><td>{stock.exchange}</td><td><span className="badge">{stock.status}</span></td><td>{stock.status === 'ACTIVE' ? <><button className="small-button" onClick={() => beginEdit(stock)}>Edit</button><button className="small-button" onClick={() => softDelete(stock.id)}>Soft-delete</button></> : <span className="muted small">Immutable state</span>}</td></tr>)}</tbody></table></div></section>
    <div className="grid-two">
      <section className="panel"><div className="panel-head"><h2>Pending settlement queue</h2><span className="muted">Stub execution</span></div><div className="table-wrap"><table><thead><tr><th>Order</th><th>Customer</th><th>Side</th><th>Qty</th><th>Quote</th><th>Action</th></tr></thead><tbody>{orderRows.filter(o => o.status === 'PENDING').map(order => <tr key={order.id}><td>{order.id.slice(0, 8)}</td><td>{userRows.find(u => u.id === order.customer_id)?.email ?? order.customer_id.slice(0, 8)}</td><td>{order.side}</td><td>{order.quantity}</td><td>{formatMoney(order.quote_price)}</td><td className="actions">{rejectingId === order.id ? <div className="reject-row"><input aria-label="Rejection reason" placeholder="Reason shown to the customer" value={rejectReason} onChange={e => setRejectReason(e.target.value)} /><button className="small-button danger-outline" onClick={() => reject(order.id)}>Confirm reject</button><button className="small-button" onClick={() => { setRejectingId(null); setRejectReason('') }}>Cancel</button></div> : <><button className="small-button" onClick={() => execute(order.id)}>Execute</button><button className="small-button danger-outline" onClick={() => { setRejectingId(order.id); setRejectReason(''); setError('') }}>Reject</button></>}</td></tr>)}</tbody></table></div></section>
      <section className="panel"><div className="panel-head"><h2>Most-traded symbols</h2><span className="muted">Executed orders, platform-wide</span></div>{stats?.most_traded_stocks.length ? <div className="table-wrap"><table><thead><tr><th>Symbol</th><th>Executed orders</th></tr></thead><tbody>{stats.most_traded_stocks.map(item => <tr key={item.stock_id}><td><strong>{item.symbol}</strong></td><td>{item.executed_order_count}</td></tr>)}</tbody></table></div> : <div className="muted small">No executed orders yet.</div>}</section>
    </div>
  </Layout>
}

function Metric({ label, value }: { label: string; value: string }) { return <div className="metric-card"><span className="eyebrow">{label}</span><strong>{value}</strong></div> }
