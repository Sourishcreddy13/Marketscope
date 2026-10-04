// Presentation helpers for authoritative decimal strings from the API.
// Financial values are never converted to JavaScript `number` (NFR-01): they are parsed and
// rounded as decimal text, using the same ROUND_HALF_UP (ties away from zero) as the backend.

const DECIMAL_PATTERN = /^([+-])?(\d+)(?:\.(\d+))?$/

type Rounded = { negative: boolean; whole: string; fraction: string }

function roundDecimal(value: string, places: number): Rounded | null {
  const match = DECIMAL_PATTERN.exec(value.trim())
  if (!match) return null
  const [, sign, whole, fraction = ''] = match
  const kept = BigInt(whole + fraction.slice(0, places).padEnd(places, '0'))
  const roundUp = (fraction[places] ?? '0') >= '5'
  const scaled = (kept + (roundUp ? 1n : 0n)).toString().padStart(places + 1, '0')
  const cut = scaled.length - places
  const roundedWhole = scaled.slice(0, cut)
  const roundedFraction = scaled.slice(cut)
  const isZero = /^0*$/.test(roundedWhole + roundedFraction)
  return { negative: sign === '-' && !isZero, whole: roundedWhole, fraction: roundedFraction }
}

function withText(rounded: Rounded, groupThousands: boolean): string {
  const whole = groupThousands ? rounded.whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : rounded.whole
  return `${rounded.negative ? '-' : ''}${whole}.${rounded.fraction}`
}

export function formatMoney(value: string): string {
  const rounded = roundDecimal(value, 2)
  if (!rounded) return '—'
  const text = withText(rounded, true)
  return rounded.negative ? `-₹${text.slice(1)}` : `₹${text}`
}

export function formatPercent(value: string): string {
  const rounded = roundDecimal(value, 2)
  return rounded ? `${withText(rounded, false)}%` : '—'
}

/** True when the decimal string is strictly negative after display rounding. */
export function isNegativeDecimal(value: string): boolean {
  return roundDecimal(value, 2)?.negative ?? false
}

/** CSS width for a 0–100 percentage bar, computed on decimal text and clamped. */
export function percentBarWidth(value: string): string {
  const rounded = roundDecimal(value, 2)
  if (!rounded || rounded.negative) return '0%'
  if (BigInt(rounded.whole) >= 100n) return '100%'
  return `${withText(rounded, false)}%`
}

// Compare two decimal strings exactly (no binary floating point). Missing values sort as zero.
export function compareDecimal(a: string | null | undefined, b: string | null | undefined): number {
  const scale = (value: string | null | undefined): bigint => {
    const text = (value ?? '0').trim()
    const negative = text.startsWith('-')
    const [whole, fraction = ''] = text.replace(/^[-+]/, '').split('.')
    const digits = BigInt(`${whole || '0'}${fraction.padEnd(8, '0').slice(0, 8)}`)
    return negative ? -digits : digits
  }
  const left = scale(a), right = scale(b)
  return left === right ? 0 : left < right ? -1 : 1
}
