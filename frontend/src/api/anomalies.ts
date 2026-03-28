import api from './client'
import type { AnomalyEvent, AnomalyStats, PaginatedResponse } from '../types/api'

export async function fetchAnomalies(params: {
  asset_id?: string
  severity?: string
  anomaly_type?: string
  is_resolved?: boolean
  limit?: number
  offset?: number
} = {}): Promise<PaginatedResponse<AnomalyEvent>> {
  const { data } = await api.get('/anomalies', { params })
  return data
}

export async function fetchAnomalyStats(): Promise<AnomalyStats> {
  const { data } = await api.get('/anomalies/stats')
  return data
}
