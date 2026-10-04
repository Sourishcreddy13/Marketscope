import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import Layout from '../components/Layout'
import { stocks, quotes, type Quote, type Stock } from '../lib/api'
import { compareDecimal, formatMoney } from '../lib/format'
import { useRequiredUser } from '../lib/session'
import { usePolling } from '../lib/usePolling'

export default function CatalogPage() {
  const user = useRequiredUser()
  const [stockRows, setStockRows] = useState<Stock[]>([])
  const [quoteRows, setQuoteRows] = useState<Quote[]>([])
  const [query, setQuery] = useState('')
  const [sector, setSector] = useState('ALL')
  const [exchange, setExchange] = useState('ALL')
  const [movement, setMovement] = useState<'ALL' | 'UP' | 'DOWN'>('ALL')
  const [sort, setSort] = useState<'SYMBOL' | 'PRICE_DESC' | 'PRICE_ASC' | 'GAINERS' | 'LOSERS'>('SYMBOL')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async (search: string) => {
    setLoading(true)
    setError('')
    try {
      const [catalog, market] = await Promise.all([stocks(search), quotes()])
      setStockRows(catalog)
      setQuoteRows(market)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load stock catalog')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh('')
  }, [refresh])

  // Poll only the prices; the searched/filtered catalog rows stay as the user left them.
  usePolling(async isActive => {
    const market = await quotes()
    if (isActive()) setQuoteRows(market)
  })

  const quoteByStock = useMemo(
    () => Object.fromEntries(quoteRows.map(quote => [quote.stock_id, quote])),
    [quoteRows],
  )

  const sectors = useMemo(
    () => ['ALL', ...new Set(stockRows.map(stock => stock.sector).sort())],
    [stockRows],
  )

  const exchanges = useMemo(
    () => ['ALL', ...new Set(stockRows.map(stock => stock.exchange).sort())],
    [stockRows],
  )

  const filtered = useMemo(() => {
    const change = (id: string) => quoteByStock[id]?.change_percent
    const price = (id: string) => quoteByStock[id]?.price
    const rows = stockRows.filter(stock =>
      (sector === 'ALL' || stock.sector === sector) &&
      (exchange === 'ALL' || stock.exchange === exchange) &&
      (movement === 'ALL' || compareDecimal(change(stock.id), '0') === (movement === 'UP' ? 1 : -1)),
    )
    const order: Record<typeof sort, (a: Stock, b: Stock) => number> = {
      SYMBOL: (a, b) => a.symbol.localeCompare(b.symbol),
      PRICE_DESC: (a, b) => compareDecimal(price(b.id), price(a.id)),
      PRICE_ASC: (a, b) => compareDecimal(price(a.id), price(b.id)),
      GAINERS: (a, b) => compareDecimal(change(b.id), change(a.id)),
      LOSERS: (a, b) => compareDecimal(change(a.id), change(b.id)),
    }
    return [...rows].sort(order[sort])
  }, [stockRows, sector, exchange, movement, sort, quoteByStock])

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    refresh(query.trim())
  }

  return (
    <Layout email={user.email} role={user.role}>
      <section className="hero">
        <div>
          <span className="eyebrow">STOCK CATALOG</span>
          <h1>Explore the market universe</h1>
          <p className="muted">
            Search synthetic symbols by symbol, company, sector, or exchange before opening an order ticket.
          </p>
        </div>
        <button className="primary" type="button" onClick={() => refresh(query.trim())} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh prices'}
        </button>
      </section>

      {error && <div className="alert error page-alert">{error}</div>}

      <section className="panel page-section">
        <form className="catalog-toolbar" onSubmit={submitSearch}>
          <label className="catalog-search">
            Search
            <input
              value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder="AAPL, Apple, Technology, NASDAQ…"
              aria-label="Search stocks"
            />
          </label>
          <label>
            Sector
            <select value={sector} onChange={event => setSector(event.target.value)}>
              {sectors.map(value => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label>
            Exchange
            <select value={exchange} onChange={event => setExchange(event.target.value)}>
              {exchanges.map(value => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label>
            Price move
            <select value={movement} onChange={event => setMovement(event.target.value as typeof movement)}>
              <option value="ALL">All</option><option value="UP">Rising</option><option value="DOWN">Falling</option>
            </select>
          </label>
          <label>
            Sort by
            <select value={sort} onChange={event => setSort(event.target.value as typeof sort)}>
              <option value="SYMBOL">Symbol A–Z</option><option value="PRICE_DESC">Price high → low</option><option value="PRICE_ASC">Price low → high</option>
              <option value="GAINERS">Biggest gainers</option><option value="LOSERS">Biggest losers</option>
            </select>
          </label>
          <button className="primary catalog-search-button" type="submit">Search</button>
        </form>
      </section>

      <section className="panel page-section">
        <div className="panel-head">
          <h2>{filtered.length} active symbols</h2>
          <span className="muted">Synthetic market data</span>
        </div>
        {filtered.length === 0 ? (
          <div className="empty-state">
            <strong>No matching symbols</strong>
            <span className="muted">Change the search or filters and try again.</span>
          </div>
        ) : (
          <div className="catalog-grid">
            {filtered.map(stock => {
              const quote = quoteByStock[stock.id]
              return (
                <article className="catalog-card" key={stock.id}>
                  <div className="panel-head">
                    <div>
                      <strong className="catalog-symbol">{stock.symbol}</strong>
                      <div className="muted small">{stock.name}</div>
                    </div>
                    <span className="badge">{stock.exchange}</span>
                  </div>
                  <div className="catalog-price">
                    <span className="eyebrow">LAST PRICE</span>
                    <strong>{quote ? formatMoney(quote.price) : '—'}</strong>
                    {quote?.change_percent && <span className={quote.change_percent.startsWith('-') ? 'negative' : 'positive'}> {quote.change_percent.startsWith('-') ? '▼' : '▲'} {quote.change_percent.replace('-', '')}% since last update</span>}
                  </div>
                  <div className="catalog-meta">
                    <span>{stock.sector}</span>
                    <span>{quote?.occurred_at ? `Updated ${new Date(quote.occurred_at.endsWith('Z') ? quote.occurred_at : quote.occurred_at + 'Z').toLocaleTimeString()}` : 'No tick'}</span>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </section>
    </Layout>
  )
}
