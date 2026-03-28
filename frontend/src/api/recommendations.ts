import api from './client'
import type { Recommendation, PaginatedResponse } from '../types/api'

export async function fetchRecommendations(params: {
  asset_class?: string
  recommendation_type?: string
  status?: string
  limit?: number
  offset?: number
} = {}): Promise<PaginatedResponse<Recommendation>> {
  const { data } = await api.get('/recommendations', { params })
  return data
}

export async function fetchActiveRecommendations(params: {
  asset_class?: string
  min_score?: number
} = {}): Promise<Recommendation[]> {
  const { data } = await api.get('/recommendations/active', { params })
  return data
}

export async function fetchRecommendation(id: string): Promise<Recommendation> {
  const { data } = await api.get(`/recommendations/${id}`)
  return data
}

export async function fetchAssetRecommendation(assetId: string): Promise<Recommendation | null> {
  const { data } = await api.get(`/assets/${assetId}/recommendation`)
  return data
}
