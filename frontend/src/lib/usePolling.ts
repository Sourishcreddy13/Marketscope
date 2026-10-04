import { useEffect, useRef } from 'react'
import { resolvePollInterval, startPolling } from './poller'

export const MARKET_POLL_INTERVAL_MS = resolvePollInterval(import.meta.env.VITE_MARKET_POLL_INTERVAL_MS)

/** Polls `task` while the component is mounted; the timer is cleared on unmount. */
export function usePolling(task: (isActive: () => boolean) => Promise<void>, intervalMs: number = MARKET_POLL_INTERVAL_MS) {
  const latest = useRef(task)
  useEffect(() => { latest.current = task })
  useEffect(() => startPolling(isActive => latest.current(isActive), intervalMs), [intervalMs])
}
