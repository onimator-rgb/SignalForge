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

export interface AssetIndicatorsSummary {
  interval: string
  bar_time: string
  rsi_14: number | null
  macd: MACDOut | null
  bollinger: BollingerOut | null
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
