import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { clearToken, getToken, me, onSessionExpired, setToken, type User } from './api'

type Status = 'loading' | 'authenticated' | 'anonymous' | 'unavailable'

type SessionValue = {
  status: Status
  user: User | null
  /** Shown on the sign-in page after an automatic sign-out. */
  notice: string
  signIn: (token: string, user: User) => void
  signOut: () => void
  setUser: (user: User) => void
  retry: () => void
}

const SessionContext = createContext<SessionValue | null>(null)

/**
 * Single source of truth for authentication state. The stored token is validated against
 * `/auth/me` on startup, so a stale or revoked token never reaches a protected page.
 */
export function SessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>(() => (getToken() ? 'loading' : 'anonymous'))
  const [user, setUserState] = useState<User | null>(null)
  const [notice, setNotice] = useState('')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!getToken()) { setStatus('anonymous'); return }
    let cancelled = false
    setStatus('loading')
    me()
      .then(current => { if (!cancelled) { setUserState(current); setStatus('authenticated') } })
      .catch(() => {
        if (cancelled) return
        // A 401 already cleared the token (and flipped us to anonymous) in the API client.
        setStatus(getToken() ? 'unavailable' : 'anonymous')
      })
    return () => { cancelled = true }
  }, [attempt])

  useEffect(() => onSessionExpired(() => {
    setUserState(null)
    setStatus('anonymous')
    setNotice('Your session has expired. Please sign in again.')
  }), [])

  const signIn = useCallback((token: string, signedIn: User) => {
    setToken(token); setUserState(signedIn); setNotice(''); setStatus('authenticated')
  }, [])
  const signOut = useCallback(() => { clearToken(); setUserState(null); setNotice(''); setStatus('anonymous') }, [])
  const retry = useCallback(() => setAttempt(count => count + 1), [])

  const value = useMemo<SessionValue>(
    () => ({ status, user, notice, signIn, signOut, setUser: setUserState, retry }),
    [status, user, notice, signIn, signOut, retry],
  )
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext)
  if (!value) throw new Error('useSession must be used inside SessionProvider')
  return value
}

/** The signed-in user. Only valid beneath the `Protected` route guard. */
export function useRequiredUser(): User {
  const { user } = useSession()
  if (!user) throw new Error('useRequiredUser used outside an authenticated route')
  return user
}
