/** Client-generated idempotency key (8-64 chars, matches the backend's accepted charset). */
export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return `ms-${crypto.randomUUID()}`
  const bytes = new Uint8Array(16)
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') crypto.getRandomValues(bytes)
  else bytes.forEach((_, index) => { bytes[index] = Math.floor(Math.random() * 256) }) // precision-ok: random id, not a financial value
  return `ms-${Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')}`
}
