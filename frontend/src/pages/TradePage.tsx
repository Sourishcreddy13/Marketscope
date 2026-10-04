import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import Layout from '../components/Layout'
import { cancelOrder, createOrder, orders, quotes, stocks, type Order, type Quote, type Stock } from '../lib/api'
import { formatMoney } from '../lib/format'
import { newIdempotencyKey } from '../lib/idempotency'
import { useRequiredUser } from '../lib/session'
import { usePolling } from '../lib/usePolling'

type TicketForm = { stock_id: string; side: 'BUY' | 'SELL'; order_type: 'MARKET' | 'LIMIT'; quantity: string; limit_price: string }

export default function TradePage() {
  const user = useRequiredUser()
  const [symbols, setSymbols] = useState<Stock[]>([])
  const [quoteRows, setQuoteRows] = useState<Quote[]>([])
  const [orderRows, setOrderRows] = useState<Order[]>([])
  const [form, setForm] = useState<TicketForm>({ stock_id: '', side: 'BUY', order_type: 'MARKET', quantity: '1.0000', limit_price: '' })
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  // One key per intended order: reused if the same ticket is retried, replaced once the ticket changes or succeeds.
  const idempotencyKey = useRef<string | null>(null)
  const inFlight = useRef(false)
  // After a successful order the button stays off until the ticket is edited, so a second click cannot silently place a duplicate.
  const [justPlaced, setJustPlaced] = useState(false)

  const loadAll = useCallback(async () => {
    const [stockRows, quoteData, orderData] = await Promise.all([stocks(), quotes(), orders()])
    setSymbols(stockRows); setQuoteRows(quoteData); setOrderRows(orderData)
    setForm(current => (!current.stock_id && stockRows[0] ? { ...current, stock_id: stockRows[0].id } : current))
  }, [])
  useEffect(() => { loadAll().catch(e => setError(e.message)) }, [loadAll])

  // Keep the market watch and quote fresh by polling the REST stub.
  usePolling(async isActive => {
    const latest = await quotes()
    if (isActive()) setQuoteRows(latest)
  })

  const currentQuote = useMemo(() => quoteRows.find(q => q.stock_id === form.stock_id), [quoteRows, form.stock_id])

  function edit(patch: Partial<TicketForm>) {
    idempotencyKey.current = null
    setJustPlaced(false)
    setForm(current => ({ ...current, ...patch }))
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (inFlight.current) return
    inFlight.current = true
    setSubmitting(true); setMessage(''); setError('')
    const key = idempotencyKey.current ?? newIdempotencyKey()
    idempotencyKey.current = key
    try {
      await createOrder({ ...form, limit_price: form.order_type === 'LIMIT' ? form.limit_price : undefined }, key)
      idempotencyKey.current = null
      setMessage('Order accepted into PENDING state. Change the ticket to place another order.')
      setJustPlaced(true)
      await loadAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Order failed')
    } finally {
      inFlight.current = false
      setSubmitting(false)
    }
  }
  async function cancel(id: string) {
    setError('')
    try { await cancelOrder(id); await loadAll() } catch (err) { setError(err instanceof Error ? err.message : 'Cancellation failed') }
  }

  return <Layout email={user.email} role={user.role}>
    <section className="hero"><div><span className="eyebrow">TRADE</span><h1>Order ticket</h1><p className="muted">Market orders use the accepted quote. Limit orders execute only when the market condition is satisfied.</p></div></section>
    {error && <div className="alert error page-alert" role="alert">{error}</div>}
    <div className="grid-two">
      <section className="panel"><div className="panel-head"><h2>Place order</h2>{currentQuote && <span className="badge">Quote {formatMoney(currentQuote.price)}</span>}</div>
        <form onSubmit={submit} className="stack">
          <label>Symbol<select value={form.stock_id} onChange={e => edit({ stock_id: e.target.value })}>{symbols.map(s => <option key={s.id} value={s.id}>{s.symbol} — {s.name}</option>)}</select></label>
          <div className="form-grid"><label>Side<select value={form.side} onChange={e => edit({ side: e.target.value as 'BUY' | 'SELL' })}><option value="BUY">BUY</option><option value="SELL">SELL</option></select></label><label>Type<select value={form.order_type} onChange={e => edit({ order_type: e.target.value as 'MARKET' | 'LIMIT' })}><option value="MARKET">MARKET</option><option value="LIMIT">LIMIT</option></select></label></div>
          <label>Quantity<input inputMode="decimal" value={form.quantity} onChange={e => edit({ quantity: e.target.value })} /></label>
          {form.order_type === 'LIMIT' && <label>Limit price<input inputMode="decimal" value={form.limit_price} onChange={e => edit({ limit_price: e.target.value })} /><span className="muted small">{form.side === 'BUY' ? 'BUY: the highest price you will pay. It executes only if the market price is at or below this.' : 'SELL: the lowest price you will accept. It executes only if the market price is at or above this.'}</span></label>}
          {message && <div className="alert" role="status">{message}</div>}
          <button className="primary" type="submit" disabled={submitting || justPlaced || !form.stock_id}>{submitting ? 'Placing order…' : justPlaced ? 'Order placed' : `Place ${form.side} order`}</button>
        </form>
      </section>
      <section className="panel"><div className="panel-head"><h2>Market watch</h2><span className="muted">Synthetic REST feed</span></div><div className="quote-grid">{quoteRows.map(q => <div className="quote" key={q.stock_id}><strong>{q.symbol}</strong><span>{formatMoney(q.price)}{q.change_percent && <small className={q.change_percent.startsWith('-') ? 'negative' : 'positive'}> {q.change_percent.startsWith('-') ? '▼' : '▲'}{q.change_percent.replace('-', '')}%</small>}</span></div>)}</div></section>
    </div>
    <section className="panel page-section"><div className="panel-head"><h2>Order history</h2><span className="muted">Customer-owned orders only</span></div><div className="table-wrap"><table><thead><tr><th>Symbol</th><th>Side</th><th>Type</th><th>Qty</th><th>Quote</th><th>Status</th><th>Details</th><th>Action</th></tr></thead><tbody>{orderRows.map(o => <tr key={o.id}><td>{symbols.find(s => s.id === o.stock_id)?.symbol ?? o.stock_id.slice(0, 8)}</td><td>{o.side}</td><td>{o.order_type}</td><td>{o.quantity}</td><td>{formatMoney(o.quote_price)}</td><td><span className="badge">{o.status}</span></td><td className="small">{o.status === 'REJECTED' ? <span className="negative">Reason: {o.rejection_reason ?? 'not given'}</span> : <span className="muted">{o.limit_price ? `Limit ${formatMoney(o.limit_price)}` : '—'}</span>}</td><td>{o.status === 'PENDING' ? <button className="small-button" onClick={() => cancel(o.id)}>Cancel</button> : o.status === 'EXECUTED' ? <span className="muted small">Immutable</span> : <span className="muted small">—</span>}</td></tr>)}</tbody></table></div></section>
  </Layout>
}
