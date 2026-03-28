import api from './client'

export interface LivePriceItem {
  asset_id: string
  symbol: string
  asset_class: string
  price: number | null
  change_24h_pct: number | null
  source: string
  updated_at: string | null
  freshness: string
}

export interface LivePricesResponse {
  count: number
  live: number
  fallback: number
  items: LivePriceItem[]
}

export async function fetchLivePrices(): Promise<LivePricesResponse> {
  const { data } = await api.get('/live/prices')
  return data
}
