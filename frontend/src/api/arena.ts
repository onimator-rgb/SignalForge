import axios from 'axios'

// Arena endpoints are mounted at /arena (not under /api/v1)
const arenaApi = axios.create({
  baseURL: (import.meta.env.VITE_API_BASE_URL || '') + '/arena',
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

export interface Trader {
  id: string
  name: string
  slug: string
  llm_provider: string
  llm_model: string
  is_active: boolean
  total_decisions: number
  wins: number
  losses: number
  description: {
    name: string
    strategy: string
    model: string
    style: string
    cost: string
  }
}

export interface LeaderboardEntry {
  rank: number
  trader_id: string
  name: string
  slug: string
  llm_provider: string
  llm_model: string
  portfolio_value_usd: number
  initial_capital: number
  total_return_pct: number
  total_decisions: number
  total_trades: number
  wins: number
  losses: number
  win_rate_pct: number
  open_positions: number
  cash_available: number
}

export interface TraderDecision {
  id: string
  created_at: string
  asset_id: string
  action: string
  confidence: number
  reasoning: string
  position_size_pct: number | null
  stop_loss_price: number | null
  take_profit_price: number | null
  executed: boolean
  llm_model_used: string | null
  latency_ms: number | null
}

export interface PerformanceSnapshot {
  date: string
  portfolio_value_usd: number
  cash_usd: number
  open_positions: number
  total_return_pct: number
  daily_return_pct: number | null
  win_rate: number | null
  total_trades: number
}

export interface Comparison {
  leaderboard: LeaderboardEntry[]
  equity_curves: Record<string, { date: string; value: number; return_pct: number }[]>
  period_days: number
}

export async function fetchTraders(): Promise<Trader[]> {
  const { data } = await arenaApi.get('/traders')
  return data
}

export async function fetchLeaderboard(): Promise<LeaderboardEntry[]> {
  const { data } = await arenaApi.get('/leaderboard')
  return data
}

export async function fetchTraderDecisions(slug: string, limit = 50): Promise<TraderDecision[]> {
  const { data } = await arenaApi.get(`/traders/${slug}/decisions`, { params: { limit } })
  return data
}

export async function fetchTraderPerformance(slug: string, days = 30): Promise<PerformanceSnapshot[]> {
  const { data } = await arenaApi.get(`/traders/${slug}/performance`, { params: { days } })
  return data
}

export async function fetchComparison(days = 30): Promise<Comparison> {
  const { data } = await arenaApi.get('/comparison', { params: { days } })
  return data
}

export async function triggerEvaluation(): Promise<any> {
  const { data } = await arenaApi.post('/evaluate')
  return data
}

export async function triggerCheckExits(): Promise<any> {
  const { data } = await arenaApi.post('/check-exits')
  return data
}

export async function triggerSnapshots(): Promise<any> {
  const { data } = await arenaApi.post('/snapshots')
  return data
}
