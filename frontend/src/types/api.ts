// Types matching backend Pydantic schemas

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface LatestPrice {
  close: number
  bar_time: string
  change_24h_pct: number | null
}

export interface AssetListItem {
  id: string
  symbol: string
  name: string
  asset_class: string
  market_cap_rank: number | null
  is_active: boolean
  image_url: string | null
  latest_price: LatestPrice | null
  unresolved_anomalies: number
}

export interface MACDOut {
  macd: number
  signal: number
  histogram: number
}

export interface BollingerOut {
  upper: number
  middle: number
  lower: number
  width: number
}

export interface IndicatorHistory {
  asset_id: string
  interval: string
  bars_used: number
  rsi_14: (number | null)[]
  macd_histogram: (number | null)[]
  adx_14: (number | null)[]
  bar_times: string[]
}

export interface TimeframeSignal {
  interval: string
  rsi_signal: 'bullish' | 'bearish' | 'neutral'
  macd_signal: 'bullish' | 'bearish' | 'neutral'
  adx_trend_strength: 'strong' | 'weak' | 'none'
}

export interface AssetIndicatorsSummary {
  interval: string
  bar_time: string
  rsi_14: number | null
  macd: MACDOut | null
  bollinger: BollingerOut | null
  adx_14: number | null
  plus_di: number | null
  minus_di: number | null
  stoch_rsi_k: number | null
  stoch_rsi_d: number | null
  vwap: number | null
  bars_available: number | null
}

export interface AssetDetail {
  id: string
  symbol: string
  name: string
  provider_symbol: string
  asset_class: string
  exchange: string | null
  currency: string
  coingecko_id: string | null
  market_cap_rank: number | null
  is_active: boolean
  image_url: string | null
  metadata: Record<string, unknown>
  latest_price: LatestPrice | null
  indicators: AssetIndicatorsSummary | null
  unresolved_anomalies: number
  created_at: string
  updated_at: string
}

export interface AssetSearchResult {
  id: string
  symbol: string
  name: string
  market_cap_rank: number | null
  image_url: string | null
}

export interface PriceBar {
  time: string
  asset_id: string
  interval: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface AnomalyEvent {
  id: string
  asset_id: string
  asset_symbol: string | null
  detected_at: string
  anomaly_type: string
  severity: string
  score: number
  details: Record<string, unknown>
  timeframe: string
  is_resolved: boolean
  resolved_at: string | null
  created_at: string
}

export interface AnomalyStats {
  total: number
  unresolved: number
  by_severity: Record<string, number>
  by_type: Record<string, number>
}

export interface HealthResponse {
  status: string
  database: string
  version: string
}

export interface AlertRule {
  id: string
  asset_id: string | null
  asset_symbol: string | null
  name: string
  rule_type: string
  condition: Record<string, unknown>
  cooldown_minutes: number
  is_active: boolean
  last_triggered_at: string | null
  created_at: string
  updated_at: string
}

export interface AlertEvent {
  id: string
  alert_rule_id: string
  rule_name: string | null
  anomaly_event_id: string | null
  asset_id: string | null
  asset_symbol: string | null
  triggered_at: string
  message: string
  details: Record<string, unknown>
  is_read: boolean
  created_at: string
}

export interface AlertStats {
  total_events: number
  unread_events: number
  active_rules: number
  total_rules: number
}

export interface AnalysisReport {
  id: string
  report_type: string
  status: string
  asset_id: string | null
  asset_symbol: string | null
  anomaly_event_id: string | null
  alert_event_id: string | null
  title: string | null
  content_md: string | null
  llm_provider: string | null
  llm_model: string | null
  prompt_version: string | null
  token_usage: { input_tokens?: number; output_tokens?: number } | null
  error_message: string | null
  created_at: string
  completed_at: string | null
}

export interface Watchlist {
  id: string
  name: string
  description: string | null
  asset_count: number
  created_at: string
  updated_at: string
}

export interface WatchlistAsset {
  asset_id: string
  symbol: string
  name: string
  asset_class: string
  image_url: string | null
  added_at: string
  latest_price: number | null
  change_24h_pct: number | null
  rec_type: string | null
  rec_score: number | null
  in_portfolio: boolean
}

export interface Recommendation {
  id: string
  asset_id: string
  asset_symbol: string | null
  asset_class: string | null
  generated_at: string
  recommendation_type: string
  score: number
  confidence: string
  risk_level: string
  rationale_summary: string
  signal_breakdown: Record<string, { score: number; weight: number; detail: string }>
  entry_price_snapshot: number | null
  time_horizon: string
  valid_until: string | null
  status: string
  created_at: string
}

export interface PortfolioPosition {
  id: string
  asset_id: string
  asset_symbol: string | null
  asset_class: string | null
  entry_price: number
  quantity: number
  entry_value_usd: number
  opened_at: string
  exit_price: number | null
  close_reason: string | null
  realized_pnl_usd: number | null
  realized_pnl_pct: number | null
  status: string
  current_price: number | null
  current_value_usd: number | null
  unrealized_pnl_usd: number | null
  unrealized_pnl_pct: number | null
  stop_loss_price: number | null
  take_profit_price: number | null
  peak_price: number | null
  peak_pnl_pct: number | null
  trailing_stop_price: number | null
  break_even_armed: boolean
  dist_stop_pct: number
  dist_target_pct: number
  hours_open: number
  hours_remaining: number
  max_hold_until: string | null
  badges: string[]
  exit_context: {
    trailing_tp_armed?: boolean
    trailing_tp_peak?: number
    trailing_buy_phase?: boolean
    entry_slippage?: {
      market_price: number
      slippage_pct: number
      adjusted_price: number
    }
  } | null
  recommendation?: {
    id: string | null
    score: number | null
    type: string | null
    rationale: string | null
    scoring_version: string | null
  } | null
}

export interface PortfolioStats {
  initial_capital: number
  current_cash: number
  equity: number
  total_return_pct: number
  open_positions: number
  closed_positions: number
  total_trades: number
  win_rate: number | null
  avg_return_pct: number | null
  best_trade_pct: number | null
  worst_trade_pct: number | null
  total_realized_pnl: number
}

export interface PortfolioTransaction {
  id: string
  tx_type: string
  asset_symbol: string | null
  price: number
  quantity: number
  value_usd: number
  executed_at: string
}

export interface RiskMetrics {
  sharpe_ratio: number | null
  sortino_ratio: number | null
  max_drawdown_pct: number
  profit_factor: number | null
  avg_hold_hours: number
  total_closed: number
  wins: number
  losses: number
  win_rate: number | null
  breakdown_by_reason: Record<string, number>
}

export interface PortfolioSummary {
  stats: PortfolioStats
  open_positions: PortfolioPosition[]
  recent_closed: PortfolioPosition[]
  recent_transactions: PortfolioTransaction[]
}

export interface ProtectionEventItem {
  id: string
  type: string
  status: string
  asset_class: string | null
  reason: string
  triggered_at: string
  expires_at: string | null
}

export interface ProtectionsResponse {
  active: ProtectionEventItem[]
  count: number
}
