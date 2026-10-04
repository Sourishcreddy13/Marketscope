import { describe, expect, it } from 'vitest'
import { compareDecimal, formatMoney, formatPercent, isNegativeDecimal, percentBarWidth } from './format'

describe('formatMoney', () => {
  it('formats positive rupee values', () => expect(formatMoney('12345.6700')).toBe('₹12,345.67'))
  it('formats negative values without using floating point arithmetic', () => expect(formatMoney('-1234.5000')).toBe('-₹1,234.50'))
  it('rounds half up instead of truncating', () => expect(formatMoney('12.3450')).toBe('₹12.35'))
  it('keeps exact digits for values beyond double precision', () => {
    expect(formatMoney('12345678901234567890.1250')).toBe('₹12,345,678,901,234,567,890.13')
  })
  it('does not render negative zero', () => expect(formatMoney('-0.0040')).toBe('₹0.00'))
  it('rejects non-decimal input visibly', () => expect(formatMoney('abc')).toBe('—'))
})

describe('formatPercent', () => {
  it('formats decimal percentage strings for presentation', () => expect(formatPercent('12.3456')).toBe('12.35%'))
  it('formats zero consistently', () => expect(formatPercent('0.0000')).toBe('0.00%'))
  it('rounds ties away from zero like the backend ROUND_HALF_UP', () => {
    expect(formatPercent('1.0050')).toBe('1.01%')
    expect(formatPercent('-1.0050')).toBe('-1.01%')
  })
  it('does not lose precision on large or highly precise values', () => {
    expect(formatPercent('9007199254740993.1234')).toBe('9007199254740993.12%')
    expect(formatPercent('0.1000000000000000055511151231257827')).toBe('0.10%')
  })
  it('normalizes negative zero', () => expect(formatPercent('-0.0001')).toBe('0.00%'))
  it('handles values that round up across a digit boundary', () => expect(formatPercent('99.9950')).toBe('100.00%'))
  it('rejects non-decimal input visibly', () => expect(formatPercent('NaN')).toBe('—'))
})

describe('isNegativeDecimal', () => {
  it('detects strictly negative values', () => {
    expect(isNegativeDecimal('-0.0500')).toBe(true)
    expect(isNegativeDecimal('-0.0001')).toBe(false)
    expect(isNegativeDecimal('3.0000')).toBe(false)
  })
})

describe('percentBarWidth', () => {
  it('clamps to the 0-100 range using decimal text', () => {
    expect(percentBarWidth('42.5000')).toBe('42.50%')
    expect(percentBarWidth('100.0000')).toBe('100%')
    expect(percentBarWidth('250.0000')).toBe('100%')
    expect(percentBarWidth('-5.0000')).toBe('0%')
  })
})

describe('compareDecimal', () => {
  it('orders decimal strings exactly, including negatives and missing values', () => {
    expect(compareDecimal('0.1', '0.10')).toBe(0)
    expect(compareDecimal('-0.0001', '0')).toBe(-1)
    expect(compareDecimal('225.0001', '225')).toBe(1)
    expect(compareDecimal(null, '0')).toBe(0)
    expect(compareDecimal('9007199254740993.0001', '9007199254740993')).toBe(1)
  })
})
