import api from './client'
import type { HealthResponse } from '../types/api'

export async function fetchHealth(): Promise<HealthResponse> {
  const { data } = await api.get('/health')
  return data
}
