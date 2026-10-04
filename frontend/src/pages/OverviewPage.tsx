import { useCallback, useEffect, useState } from 'react'
import Layout from '../components/Layout'
import MetricCard from '../components/MetricCard'
import { dailyStats, portfolio, sectorExposure, type DailyStats, type Portfolio, type SectorExposure } from '../lib/api'
import { formatMoney, formatPercent, isNegativeDecimal, percentBarWidth } from '../lib/format'
import { useRequiredUser } from '../lib/session'

type Panel<T> = { data: T | null; error: string; loading: boolean }
const idle = <T,>(): Panel<T> => ({ data: null, error: '', loading: true })
const message = (e: unknown, fallback: string) => (e instanceof Error ? e.message : fallback)

export default function OverviewPage() {
  const user = useRequiredUser()
  // The portfolio is critical; daily movers and sector exposure are optional and fail independently.
  const [data, setData] = useState<Panel<Portfolio>>(idle)
  const [daily, setDaily] = useState<Panel<DailyStats>>(idle)
  const [sectors, setSectors] = useState<Panel<SectorExposure[]>>(idle)

  const loadPortfolio = useCallback(() => {
    setData(idle())
    portfolio().then(p => setData({ data: p, error: '', loading: false })).catch(e => setData({ data: null, error: message(e, 'Failed to load portfolio'), loading: false }))
  }, [])
  const loadDaily = useCallback(() => {
    setDaily(idle())
    dailyStats().then(d => setDaily({ data: d, error: '', loading: false })).catch(e => setDaily({ data: null, error: message(e, 'Daily movers are unavailable'), loading: false }))
  }, [])
  const loadSectors = useCallback(() => {
    setSectors(idle())
    sectorExposure().then(s => setSectors({ data: s, error: '', loading: false })).catch(e => setSectors({ data: null, error: message(e, 'Sector exposure is unavailable'), loading: false }))
  }, [])
  useEffect(() => { loadPortfolio(); loadDaily(); loadSectors() }, [loadPortfolio, loadDaily, loadSectors])

  const portfolioData = data.data
  return <Layout email={user.email} role={user.role}>
    <section className="hero"><div><span className="eyebrow">PORTFOLIO OVERVIEW</span><h1>Welcome back, {user.email.split('@')[0]}</h1><p className="muted">Server-side fixed-point valuation with synthetic market data.</p></div></section>
    {data.error && <div className="alert error page-alert" role="alert">{data.error} <button className="link-button" onClick={loadPortfolio}>Retry</button></div>}
    {data.loading && !portfolioData && <div className="muted page-alert">Loading portfolio…</div>}
    {portfolioData && <PortfolioMetrics data={portfolioData} />}
    <div className="grid-two">
      <section className="panel"><div className="panel-head"><h2>Current holdings</h2><span className="badge">{portfolioData?.holdings.length ?? 0} positions</span></div>
        <div className="table-wrap"><table><thead><tr><th>Symbol</th><th>Qty</th><th>Avg</th><th>Price</th><th>P&L</th></tr></thead><tbody>{(portfolioData?.holdings ?? []).map(h => <tr key={h.stock_id}><td><strong>{h.symbol}</strong></td><td>{h.quantity}</td><td>{formatMoney(h.average_buy_price)}</td><td>{formatMoney(h.current_price)}</td><td className={!isNegativeDecimal(h.absolute_pnl) ? 'positive' : 'negative'}>{formatMoney(h.absolute_pnl)} · {formatPercent(h.percent_pnl)}</td></tr>)}</tbody></table></div>
      </section>
      <section className="panel"><div className="panel-head"><h2>Daily movers</h2><span className="muted">Top 5</span></div>
        {daily.error ? <Unavailable text={daily.error} onRetry={loadDaily} /> : daily.loading ? <div className="muted small">Loading…</div> : <>
          <h3>Gainers</h3>{daily.data?.top_5_gainers.length ? daily.data.top_5_gainers.map(x => <div className="mover" key={x.stock_id}><span>{x.symbol}</span><strong className="positive">{formatPercent(x.percent_pnl)}</strong></div>) : <div className="muted small">No gainers yet.</div>}
          <h3>Losers</h3>{daily.data?.top_5_losers.length ? daily.data.top_5_losers.map(x => <div className="mover" key={x.stock_id}><span>{x.symbol}</span><strong className="negative">{formatPercent(x.percent_pnl)}</strong></div>) : <div className="muted small">No losers yet.</div>}
        </>}
      </section>
    </div>
    <section className="panel page-section"><div className="panel-head"><h2>Sector exposure</h2><span className="muted">Current market value</span></div>
      {sectors.error ? <Unavailable text={sectors.error} onRetry={loadSectors} /> : sectors.loading ? <div className="muted small">Loading…</div> : sectors.data?.length ? sectors.data.map(item => <div className="exposure" key={item.sector}><div className="exposure-row"><span>{item.sector}</span><strong>{formatPercent(item.percent)}</strong></div><div className="bar"><span style={{ width: percentBarWidth(item.percent) }} /></div><div className="muted small">{formatMoney(item.value)}</div></div>) : <div className="muted">No holdings yet. Place and execute a trade to populate analytics.</div>}
    </section>
  </Layout>
}

function PortfolioMetrics({ data }: { data: Portfolio }) {
  const tone = isNegativeDecimal(data.absolute_pnl) ? 'negative' : 'positive'
  return <div className="metric-grid">
    <MetricCard label="Current value" value={formatMoney(data.current_value)} />
    <MetricCard label="Invested" value={formatMoney(data.total_invested)} />
    <MetricCard label="Absolute P&L" value={formatMoney(data.absolute_pnl)} tone={tone} />
    <MetricCard label="P&L %" value={formatPercent(data.percent_pnl)} tone={tone} />
    <MetricCard label="Available cash" value={formatMoney(data.available_cash)} />
  </div>
}

function Unavailable({ text, onRetry }: { text: string; onRetry: () => void }) {
  return <div className="alert error" role="alert">{text} <button className="link-button" onClick={onRetry}>Retry</button></div>
}
