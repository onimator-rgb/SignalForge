import api from './client'
import type { PortfolioSummary } from '../types/api'

export async function fetchPortfolio(): Promise<PortfolioSummary> {
  const { data } = await api.get('/portfolio')
  return data
}

export async function triggerEvaluation(): Promise<{ status: string; closed: number; opened: number }> {
  const { data } = await api.post('/portfolio/evaluate')
  return data
}
