/**
 * Shared composable for live price polling.
 * Fetches /api/v1/live/prices at a given interval,
 * provides a reactive Map<symbol, LivePriceItem> and overall status.
 * Auto-cleans on unmount.
 */

import { ref, onMounted, onUnmounted } from 'vue'
import { fetchLivePrices, type LivePriceItem } from '../api/live'

export function useLivePrices(intervalMs = 15_000) {
  const prices = ref<Map<string, LivePriceItem>>(new Map())
  const status = ref<'loading' | 'live' | 'delayed' | 'error'>('loading')
  let timer: ReturnType<typeof setInterval> | null = null

  async function refresh() {
    try {
      const res = await fetchLivePrices()
      const map = new Map<string, LivePriceItem>()
      for (const item of res.items) {
        map.set(item.symbol, item)
      }
      prices.value = map
      status.value = res.live > 0 ? 'live' : 'delayed'
    } catch {
      status.value = 'error'
    }
  }

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

  onMounted(() => {
    refresh()
    timer = setInterval(refresh, intervalMs)
  })

  onUnmounted(() => {
    if (timer) clearInterval(timer)
  })

  return { prices, status, refresh, get, getPrice, getChange, getFreshness }
}
