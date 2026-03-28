import api from './client'
import type {
  AssetDetail,
  AssetListItem,
  AssetSearchResult,
  PaginatedResponse,
  PriceBar,
} from '../types/api'

export async function fetchAssets(params: {
  active_only?: boolean
  asset_class?: string
  sort_by?: string
  sort_dir?: string
  limit?: number
  offset?: number
} = {}): Promise<PaginatedResponse<AssetListItem>> {
  const { data } = await api.get('/assets', { params })
  return data
}

export async function fetchAssetDetail(id: string): Promise<AssetDetail> {
  const { data } = await api.get(`/assets/${id}`)
  return data
}

export async function searchAssets(q: string, limit = 10): Promise<AssetSearchResult[]> {
  const { data } = await api.get('/assets/search', { params: { q, limit } })
  return data
}

export async function fetchOHLCV(
  assetId: string,
  interval = '1h',
  limit = 100,
): Promise<PriceBar[]> {
  const { data } = await api.get(`/assets/${assetId}/ohlcv`, {
    params: { interval, limit },
  })
  return data
}
