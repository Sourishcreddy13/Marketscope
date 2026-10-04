/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Market-data polling interval in milliseconds (clamped to 5s–5min, default 15s). */
  readonly VITE_MARKET_POLL_INTERVAL_MS?: string
}
