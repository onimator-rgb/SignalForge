import api from './client'
import type { PortfolioSummary, ProtectionEvent, RiskMetrics } from '../types/api'

export async function fetchPortfolio(): Promise<PortfolioSummary> {
  const { data } = await api.get('/portfolio')
  return data
}

export async function triggerEvaluation(): Promise<{ status: string; closed: number; opened: number }> {
  const { data } = await api.post('/portfolio/evaluate')
  return data
}

export async function fetchProtectionHistory(limit = 20): Promise<ProtectionEvent[]> {
  const { data } = await api.get(`/portfolio/protection-history?limit=${limit}`)
  return data
}

export async function fetchRiskMetrics(): Promise<RiskMetrics> {
  const { data } = await api.get('/portfolio/risk-metrics')
  return data
}
