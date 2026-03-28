import api from './client'
import type { Watchlist, WatchlistAsset } from '../types/api'

export async function fetchWatchlists(): Promise<Watchlist[]> {
  const { data } = await api.get('/watchlists')
  return data
}

export async function createWatchlist(params: {
  name: string
  description?: string
}): Promise<Watchlist> {
  const { data } = await api.post('/watchlists', params)
  return data
}

export async function updateWatchlist(id: string, params: {
  name?: string
  description?: string
}): Promise<Watchlist> {
  const { data } = await api.patch(`/watchlists/${id}`, params)
  return data
}

export async function deleteWatchlist(id: string): Promise<void> {
  await api.delete(`/watchlists/${id}`)
}

export async function fetchWatchlistAssets(id: string): Promise<WatchlistAsset[]> {
  const { data } = await api.get(`/watchlists/${id}/assets`)
  return data
}

export async function addAssetToWatchlist(watchlistId: string, assetId: string): Promise<void> {
  await api.post(`/watchlists/${watchlistId}/assets`, { asset_id: assetId })
}

export async function removeAssetFromWatchlist(watchlistId: string, assetId: string): Promise<void> {
  await api.delete(`/watchlists/${watchlistId}/assets/${assetId}`)
}
