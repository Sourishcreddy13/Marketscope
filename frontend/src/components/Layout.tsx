import { useEffect, type ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useSession } from '../lib/session'

export default function Layout({ children, email, role }: { children: ReactNode; email: string; role: string }) {
  const navigate = useNavigate()
  const session = useSession()
  // Copy each column heading onto its cells so the CSS can render tables as stacked cards on phones.
  useEffect(() => {
    const label = () => document.querySelectorAll('.content table').forEach(table => {
      const heads = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent ?? '')
      table.querySelectorAll('tbody tr').forEach(row => Array.from(row.children).forEach((cell, index) => {
        if (heads[index] && cell.getAttribute('data-label') !== heads[index]) cell.setAttribute('data-label', heads[index])
      }))
    })
    label()
    const observer = new MutationObserver(label)
    observer.observe(document.querySelector('.content') as Node, { childList: true, subtree: true })
    return () => observer.disconnect()
  }, [])
  function signOut() { session.signOut(); navigate('/login', { replace: true }) }
  return (
    <div className="shell">
      <aside className="sidebar">
        <div>
          <div className="brand">MarketScope</div>
          <p className="muted small">Retail trading & analytics</p>
        </div>
        <nav>
          <NavLink to="/" end>Overview</NavLink>
          <NavLink to="/catalog">Catalog</NavLink>
          <NavLink to="/trade">Trade</NavLink>
          <NavLink to="/watchlists">Watchlists</NavLink>
          <NavLink to="/profile">Profile</NavLink>
          {role === 'ADMIN' && <NavLink to="/admin">Admin</NavLink>}
        </nav>
        <button className="ghost danger" onClick={signOut}>Sign out</button>
      </aside>
      <main className="content">
        <header className="topbar">
          <div><span className="eyebrow">ACCOUNT</span><strong>{email}</strong></div>
          <span className={`role role-${role.toLowerCase()}`}>{role}</span>
        </header>
        {children}
      </main>
    </div>
  )
}
