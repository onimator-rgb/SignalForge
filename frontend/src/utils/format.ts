/**
 * Format a price for display. Handles very small prices (SHIB, PEPE)
 * and very large prices (BTC) gracefully.
 */
export function fmtPrice(n: number): string {
  if (n === 0) return '0'
  if (n >= 10_000) return n.toLocaleString('en-US', { maximumFractionDigits: 0 })
  if (n >= 1) return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  if (n >= 0.01) return n.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 4 })
  if (n >= 0.0001) return n.toLocaleString('en-US', { minimumFractionDigits: 6, maximumFractionDigits: 6 })
  // Very small prices (SHIB, PEPE): use subscript notation or full decimals
  return n.toLocaleString('en-US', { minimumFractionDigits: 8, maximumFractionDigits: 8 })
}

/**
 * Format a price with more detail for OHLCV tables.
 */
export function fmtPriceDetail(n: number): string {
  if (n >= 1000) return n.toLocaleString('en-US', { maximumFractionDigits: 2 })
  if (n >= 1) return n.toLocaleString('en-US', { maximumFractionDigits: 4 })
  if (n >= 0.01) return n.toLocaleString('en-US', { maximumFractionDigits: 6 })
  return n.toLocaleString('en-US', { maximumFractionDigits: 8 })
}

/**
 * Format volume with K/M/B suffix.
 */
export function fmtVol(n: number): string {
  if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B'
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M'
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K'
  return n.toFixed(0)
}

/**
 * Format ISO timestamp for display.
 */
export function fmtTime(iso: string): string {
  return new Date(iso).toLocaleString('pl-PL', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

/**
 * Relative time ago string.
 */
export function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'teraz'
  if (mins < 60) return `${mins}m temu`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h temu`
  return `${Math.floor(hrs / 24)}d temu`
}
