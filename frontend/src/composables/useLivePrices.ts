/**
 * Shared composable for live prices.
 *
 * Primary: SSE stream from /api/v1/live/stream (real-time push).
 * Fallback: REST polling /api/v1/live/prices (if SSE disconnects).
 * Initial: REST snapshot on mount, then SSE takes over.
 */

import { ref, onMounted, onUnmounted } from 'vue'
import { fetchLivePrices, type LivePriceItem } from '../api/live'

const SSE_URL = '/api/v1/live/stream'
const FALLBACK_POLL_MS = 30_000  // Slow fallback if SSE fails

export function useLivePrices(_intervalMs = 15_000) {
  const prices = ref<Map<string, LivePriceItem>>(new Map())
  const status = ref<'loading' | 'live' | 'streaming' | 'delayed' | 'error'>('loading')
  let eventSource: EventSource | null = null
  let fallbackTimer: ReturnType<typeof setInterval> | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  // ── REST snapshot (initial + fallback) ─────────
  async function fetchSnapshot() {
    try {
      const res = await fetchLivePrices()
      const map = new Map<string, LivePriceItem>()
      for (const item of res.items) {
        map.set(item.symbol, item)
      }
      prices.value = map
      if (status.value === 'loading') {
        status.value = res.live > 0 ? 'live' : 'delayed'
      }
    } catch {
      if (status.value === 'loading') status.value = 'error'
    }
  }

  // ── SSE stream ─────────────────────────────────
  function connectSSE() {
    if (eventSource) return

    const baseUrl = window.location.hostname === 'localhost'
      ? 'http://localhost:8000'
      : ''

    eventSource = new EventSource(baseUrl + SSE_URL)

    eventSource.onopen = () => {
      status.value = 'streaming'
      // Stop fallback polling when SSE is active
      if (fallbackTimer) {
        clearInterval(fallbackTimer)
        fallbackTimer = null
      }
    }

    eventSource.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'price_batch' && Array.isArray(msg.items)) {
          // Batch update
          for (const item of msg.items as LivePriceItem[]) {
            prices.value.set(item.symbol, item)
          }
          prices.value = new Map(prices.value)
        } else if (msg.symbol) {
          // Single update (backward compat)
          prices.value.set(msg.symbol, msg as LivePriceItem)
          prices.value = new Map(prices.value)
        }
        if (status.value !== 'streaming') status.value = 'streaming'
      } catch {
        // Ignore parse errors
      }
    }

    eventSource.onerror = () => {
      // SSE disconnected — cleanup and start fallback
      if (eventSource) {
        eventSource.close()
        eventSource = null
      }
      status.value = 'delayed'

      // Start fallback polling
      if (!fallbackTimer) {
        fallbackTimer = setInterval(fetchSnapshot, FALLBACK_POLL_MS)
      }

      // Try reconnect after delay
      reconnectTimer = setTimeout(() => {
        connectSSE()
      }, 5000)
    }
  }

  // ── Helpers ────────────────────────────────────
  function get(symbol: string): LivePriceItem | undefined {
    return prices.value.get(symbol)
  }

  function getPrice(symbol: string): number | null {
    return prices.value.get(symbol)?.price ?? null
  }

  function getChange(symbol: string): number | null {
    return prices.value.get(symbol)?.change_24h_pct ?? null
  }

  function getFreshness(symbol: string): string {
    return prices.value.get(symbol)?.freshness ?? 'unavailable'
  }

  // ── Lifecycle ──────────────────────────────────
  onMounted(async () => {
    // 1. Initial REST snapshot
    await fetchSnapshot()
    // 2. Then connect SSE for push updates
    connectSSE()
  })

  onUnmounted(() => {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
    if (fallbackTimer) clearInterval(fallbackTimer)
    if (reconnectTimer) clearTimeout(reconnectTimer)
  })

  return { prices, status, get, getPrice, getChange, getFreshness, refresh: fetchSnapshot }
}
