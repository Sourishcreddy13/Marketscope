import { useCallback, useEffect, useMemo, useState } from 'react'
import Layout from '../components/Layout'
import { createWatchlist, deleteWatchlist, stocks, updateWatchlist, watchlists, type Stock, type Watchlist } from '../lib/api'
import { useRequiredUser } from '../lib/session'

export default function WatchlistsPage() {
  const user = useRequiredUser()
  const [lists, setLists] = useState<Watchlist[]>([])
  const [stockRows, setStockRows] = useState<Stock[]>([])
  const [name, setName] = useState('My Watchlist')
  const [selected, setSelected] = useState<string[]>([])
  const [editing, setEditing] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const refresh = useCallback(async () => { const [w, s] = await Promise.all([watchlists(), stocks()]); setLists(w); setStockRows(s) }, [])
  useEffect(() => { refresh().catch(e => setError(e.message)) }, [refresh])
  const symbols = useMemo(() => Object.fromEntries(stockRows.map(stock => [stock.id, stock.symbol])), [stockRows])

  function toggleStock(id: string) { setSelected(current => current.includes(id) ? current.filter(x => x !== id) : [...current, id]) }
  function beginEdit(list: Watchlist) { setEditing(list.id); setName(list.name); setSelected(list.stock_ids) }
  async function save() {
    setError(''); setMessage('')
    try {
      if (!name.trim() || selected.length === 0) throw new Error('Name and at least one symbol are required.')
      if (editing) await updateWatchlist(editing, { name: name.trim(), stock_ids: selected })
      else await createWatchlist({ name: name.trim(), stock_ids: selected })
      setEditing(null); setName('My Watchlist'); setSelected([]); setMessage(editing ? 'Watchlist updated atomically.' : 'Watchlist created.'); await refresh()
    } catch (e) { setError(e instanceof Error ? e.message : 'Watchlist operation failed') }
  }
  async function remove(id: string) { setError(''); try { await deleteWatchlist(id); if (editing === id) setEditing(null); await refresh() } catch (e) { setError(e instanceof Error ? e.message : 'Delete failed') } }
  return <Layout email={user.email} role={user.role}>
    <section className="hero"><div><span className="eyebrow">WATCHLISTS</span><h1>Curate your symbols</h1><p className="muted">Maximum 10 watchlists per customer. Each mutation is committed atomically.</p></div></section>
    <div className="content-grid">
      <section className="panel"><div className="panel-head"><h2>{editing ? 'Edit watchlist' : 'Create watchlist'}</h2><span className="badge">{lists.length} / 10</span></div>
        <div className="stack"><label>Name<input value={name} onChange={e => setName(e.target.value)} /></label><div><span className="eyebrow">SYMBOLS</span><div className="symbol-picker">{stockRows.map(stock => <label className="check" key={stock.id}><input type="checkbox" checked={selected.includes(stock.id)} onChange={() => toggleStock(stock.id)} /> <span><strong>{stock.symbol}</strong> <span className="muted small">{stock.sector}</span></span></label>)}</div></div>{message && <div className="alert" role="status">{message}</div>}{error && <div className="alert error" role="alert">{error}</div>}<div className="button-row"><button className="primary" onClick={save}>{editing ? 'Save changes' : 'Create watchlist'}</button>{editing && <button className="ghost-inline" onClick={() => { setEditing(null); setName('My Watchlist'); setSelected([]) }}>Cancel</button>}</div></div>
      </section>
      <section className="panel"><div className="panel-head"><h2>Your watchlists</h2><span className="muted">Atomic updates</span></div>{lists.length ? <div className="stack">{lists.map(list => <article className="list-card" key={list.id}><div className="panel-head"><strong>{list.name}</strong><span className="muted small">{list.stock_ids.length} symbols</span></div><div className="chips">{list.stock_ids.map(id => <span className="chip" key={id}>{symbols[id] ?? id.slice(0, 8)}</span>)}</div><div className="button-row"><button className="ghost-inline" onClick={() => beginEdit(list)}>Edit</button><button className="ghost-inline danger" onClick={() => remove(list.id)}>Delete</button></div></article>)}</div> : <div className="muted">No watchlists yet.</div>}</section>
    </div>
  </Layout>
}
