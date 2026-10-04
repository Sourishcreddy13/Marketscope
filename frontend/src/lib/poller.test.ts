import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MAX_POLL_INTERVAL_MS, MIN_POLL_INTERVAL_MS, resolvePollInterval, startPolling } from './poller'

describe('resolvePollInterval', () => {
  it('uses the default for missing or invalid values', () => {
    expect(resolvePollInterval(undefined)).toBe(15_000)
    expect(resolvePollInterval('abc')).toBe(15_000)
    expect(resolvePollInterval(-5)).toBe(15_000)
  })
  it('clamps to the allowed bounds', () => {
    expect(resolvePollInterval(10)).toBe(MIN_POLL_INTERVAL_MS)
    expect(resolvePollInterval('99999999')).toBe(MAX_POLL_INTERVAL_MS)
    expect(resolvePollInterval('20000')).toBe(20_000)
  })
})

describe('startPolling', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('runs on the interval and stops cleanly on cleanup', async () => {
    const task = vi.fn().mockResolvedValue(undefined)
    const stop = startPolling(task, 5_000)
    await vi.advanceTimersByTimeAsync(5_000)
    await vi.advanceTimersByTimeAsync(5_000)
    expect(task).toHaveBeenCalledTimes(2)
    stop()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(task).toHaveBeenCalledTimes(2)
  })

  it('never overlaps runs', async () => {
    let running = 0
    let peak = 0
    const task = vi.fn(async () => {
      running += 1
      peak = Math.max(peak, running)
      await new Promise(resolve => setTimeout(resolve, 12_000))
      running -= 1
    })
    const stop = startPolling(task, 5_000)
    await vi.advanceTimersByTimeAsync(60_000)
    stop()
    expect(peak).toBe(1)
  })

  it('skips work while the tab is hidden but keeps scheduling', async () => {
    let visible = false
    const task = vi.fn().mockResolvedValue(undefined)
    const stop = startPolling(task, 5_000, { isVisible: () => visible })
    await vi.advanceTimersByTimeAsync(10_000)
    expect(task).not.toHaveBeenCalled()
    visible = true
    await vi.advanceTimersByTimeAsync(5_000)
    expect(task).toHaveBeenCalledTimes(1)
    stop()
  })

  it('backs off after failures and reports the error', async () => {
    const onError = vi.fn()
    const task = vi.fn().mockRejectedValue(new Error('down'))
    const stop = startPolling(task, 5_000, { onError })
    await vi.advanceTimersByTimeAsync(5_000)
    expect(task).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(5_000) // backed off to 10s: not yet
    expect(task).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(5_000)
    expect(task).toHaveBeenCalledTimes(2)
    expect(onError).toHaveBeenCalledTimes(2)
    stop()
  })

  it('tells an in-flight run to discard its result after cleanup', async () => {
    let activeAtEnd: boolean | undefined
    const task = vi.fn(async (isActive: () => boolean) => {
      await new Promise(resolve => setTimeout(resolve, 1_000))
      activeAtEnd = isActive()
    })
    const stop = startPolling(task, 5_000)
    await vi.advanceTimersByTimeAsync(5_000)
    stop()
    await vi.advanceTimersByTimeAsync(1_000)
    expect(activeAtEnd).toBe(false)
  })
})
