import api from './client'

export interface PerformanceMetrics {
  summary: {
    total_recommendations: number
    active_recommendations: number
    evaluated_24h: number
    evaluated_72h: number
    avg_return_24h_pct: number | null
    avg_return_72h_pct: number | null
  }
  by_type: Array<{
    type: string
    total: number
    evaluated: number
    avg_return_24h_pct: number | null
    avg_return_72h_pct: number | null
    accuracy_24h_pct: number | null
  }>
  by_asset_class: Array<{
    asset_class: string
    total: number
    evaluated: number
    avg_return_24h_pct: number | null
    avg_return_72h_pct: number | null
    accuracy_24h_pct: number | null
  }>
  by_score_bucket: Array<{
    bucket: string
    total: number
    evaluated: number
    avg_return_24h_pct: number | null
    avg_return_72h_pct: number | null
    accuracy_24h_pct: number | null
  }>
}

export async function fetchPerformance(): Promise<PerformanceMetrics> {
  const { data } = await api.get('/recommendations/performance')
  return data
}
