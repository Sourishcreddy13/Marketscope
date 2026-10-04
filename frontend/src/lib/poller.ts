// Bounded, overlap-free REST polling used for the synthetic market feed (WebSockets are out of scope).

export const DEFAULT_POLL_INTERVAL_MS = 15_000
export const MIN_POLL_INTERVAL_MS = 5_000
export const MAX_POLL_INTERVAL_MS = 300_000

export function resolvePollInterval(raw: string | number | undefined, fallback = DEFAULT_POLL_INTERVAL_MS): number {
  const parsed = typeof raw === 'number' ? raw : Number.parseInt(String(raw ?? ''), 10)
  const value = Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
  return Math.min(MAX_POLL_INTERVAL_MS, Math.max(MIN_POLL_INTERVAL_MS, value))
}

export type PollOptions = {
  /** Skip work while the tab is hidden. Defaults to the Page Visibility API. */
  isVisible?: () => boolean
  onError?: (error: unknown) => void
}

/**
 * Runs `task` every `intervalMs` (after the previous run finished, so runs never overlap).
 * Consecutive failures back off exponentially up to MAX_POLL_INTERVAL_MS. Returns a stop function
 * that cancels the timer; a run that is still in flight is told to discard its result via `isActive`.
 */
export function startPolling(task: (isActive: () => boolean) => Promise<void>, intervalMs: number, options: PollOptions = {}): () => void {
  const base = resolvePollInterval(intervalMs)
  const isVisible = options.isVisible ?? (() => typeof document === 'undefined' || document.visibilityState !== 'hidden')
  let stopped = false
  let failures = 0
  let timer: ReturnType<typeof setTimeout> | undefined

  const isActive = () => !stopped

  async function tick() {
    if (stopped) return
    if (isVisible()) {
      try {
        await task(isActive)
        failures = 0
      } catch (error) {
        failures += 1
        options.onError?.(error)
      }
    }
    if (!stopped) schedule()
  }

  function schedule() {
    const delay = Math.min(MAX_POLL_INTERVAL_MS, base * 2 ** Math.min(failures, 6))
    timer = setTimeout(tick, delay)
  }

  schedule()
  return () => {
    stopped = true
    if (timer !== undefined) clearTimeout(timer)
  }
}
