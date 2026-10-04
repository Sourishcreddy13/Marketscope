import { FormEvent, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { login, register } from '../lib/api'
import { useSession } from '../lib/session'

export default function LoginPage() {
  const [email, setEmail] = useState('customer@marketscope.local')
  const [password, setPassword] = useState('Customer@12345')
  const [mode, setMode] = useState<'login'|'register'>('login')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const location = useLocation()
  const session = useSession()

  async function submit(event: FormEvent) {
    event.preventDefault(); setError(''); setBusy(true)
    try {
      const result = mode === 'login' ? await login(email, password) : await register(email, password)
      session.signIn(result.access_token, result.user)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    } finally { setBusy(false) }
  }

  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname || '/'
  if (session.status === 'authenticated') return <Navigate to={from} replace />

  return <div className="auth-page">
    <section className="auth-card">
      <div className="brand">MarketScope</div>
      <span className="eyebrow">SELF-SERVICE BROKERAGE</span>
      <h1>{mode === 'login' ? 'Sign in' : 'Create customer account'}</h1>
      <p className="muted">Synthetic demo environment. Prices and order execution are stubbed.</p>
      <form onSubmit={submit} className="stack">
        <label>Email<input value={email} onChange={e => setEmail(e.target.value)} type="email" required /></label>
        <label>Password<input value={password} onChange={e => setPassword(e.target.value)} type="password" required minLength={8} /></label>
        {(error || session.notice) && <div className="alert error" role="alert">{error || session.notice}</div>}
        <button className="primary" type="submit" disabled={busy}>{busy ? 'Working…' : mode === 'login' ? 'Sign in' : 'Register'}</button>
      </form>
      <button className="link-button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>
        {mode === 'login' ? 'Need an account? Register' : 'Already have an account? Sign in'}
      </button>
    </section>
  </div>
}
