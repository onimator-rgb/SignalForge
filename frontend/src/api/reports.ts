import api from './client'
import type { AnalysisReport, PaginatedResponse } from '../types/api'

export async function generateReport(params: {
  report_type: string
  asset_id?: string
  anomaly_event_id?: string
}): Promise<AnalysisReport> {
  const { data } = await api.post('/reports/generate', params)
  return data
}

export async function fetchReports(params: {
  report_type?: string
  limit?: number
  offset?: number
} = {}): Promise<PaginatedResponse<AnalysisReport>> {
  const { data } = await api.get('/reports', { params })
  return data
}

export async function fetchReport(id: string): Promise<AnalysisReport> {
  const { data } = await api.get(`/reports/${id}`)
  return data
}

export async function retryReport(id: string): Promise<AnalysisReport> {
  const { data } = await api.post(`/reports/${id}/retry`)
  return data
}
