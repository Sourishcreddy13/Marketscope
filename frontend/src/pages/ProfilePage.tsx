import { type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import { closeAccount, updateProfile } from '../lib/api'
import { useRequiredUser, useSession } from '../lib/session'

export default function ProfilePage() {
  const user = useRequiredUser()
  const session = useSession()
  const navigate = useNavigate()
  const [email, setEmail] = useState(user.email)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [closePassword, setClosePassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault(); setMessage(''); setError('')
    try {
      const updated = await updateProfile({ email, current_password: newPassword ? currentPassword : undefined, new_password: newPassword || undefined })
      session.setUser(updated); setCurrentPassword(''); setNewPassword(''); setMessage('Profile updated.')
    } catch (e) { setError(e instanceof Error ? e.message : 'Profile update failed') }
  }

  async function close(event: FormEvent) {
    event.preventDefault(); setMessage(''); setError('')
    try {
      await closeAccount(closePassword)
      session.signOut(); navigate('/login', { replace: true })
    } catch (e) { setError(e instanceof Error ? e.message : 'Account closure failed') }
  }

  return <Layout email={user.email} role={user.role}>
    <section className="hero"><div><span className="eyebrow">PROFILE</span><h1>Account settings</h1><p className="muted">Update your email or rotate your password with the current credential.</p></div></section>
    <section className="panel page-section narrow"><form onSubmit={submit} className="stack">
      <label>Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} required /></label>
      <label>Current password<input type="password" value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} /></label>
      <label>New password<input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} minLength={8} /></label>
      {message && <div className="alert" role="status">{message}</div>}{error && <div className="alert error" role="alert">{error}</div>}
      <button className="primary" type="submit">Save profile</button>
    </form></section>
    {user.role !== 'ADMIN' && <section className="panel page-section narrow"><form onSubmit={close} className="stack">
      <div className="panel-head"><h2>Close account</h2><span className="muted">Order history is retained</span></div>
      <p className="muted small">Closing suspends sign-in. Cancel pending orders first; an administrator can reactivate the account.</p>
      <label>Confirm with your password<input type="password" value={closePassword} onChange={e => setClosePassword(e.target.value)} minLength={8} required /></label>
      <button className="small-button danger-outline" type="submit">Close my account</button>
    </form></section>}
  </Layout>
}
