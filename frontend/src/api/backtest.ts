import api from './client'

export interface BacktestRequest {
  asset_id: string
  interval?: string
  lookback_days?: number
  profile_name?: string
}

export interface TradeOut {
  entry_index: number
  exit_index: number
  entry_price: number
  exit_price: number
  side: string
  quantity: number
  pnl: number
  pnl_pct: number
  exit_reason: string
}

export interface BacktestResponse {
  total_return: number
  total_return_pct: number
  max_drawdown_pct: number
  sharpe_ratio: number
  win_rate: number
  profit_factor: number
  total_trades: number
  avg_trade_pnl_pct: number
  best_trade_pnl_pct: number
  worst_trade_pnl_pct: number
  trades: TradeOut[]
}

export async function runBacktest(req: BacktestRequest): Promise<BacktestResponse> {
  const { data } = await api.post('/backtest/run', req)
  return data
}
