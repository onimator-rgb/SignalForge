import api from './client'
import type { AlertRule, AlertEvent, AlertStats, PaginatedResponse } from '../types/api'

export async function fetchAlertRules(): Promise<AlertRule[]> {
  const { data } = await api.get('/alerts/rules')
  return data
}

export async function createAlertRule(params: {
  name: string
  rule_type: string
  condition: Record<string, unknown>
  asset_id?: string | null
  cooldown_minutes?: number
  is_active?: boolean
}): Promise<AlertRule> {
  const { data } = await api.post('/alerts/rules', params)
  return data
}

export async function updateAlertRule(id: string, params: {
  name?: string
  condition?: Record<string, unknown>
  cooldown_minutes?: number
  is_active?: boolean
}): Promise<AlertRule> {
  const { data } = await api.patch(`/alerts/rules/${id}`, params)
  return data
}

export async function deleteAlertRule(id: string): Promise<void> {
  await api.delete(`/alerts/rules/${id}`)
}

export async function fetchAlertEvents(params: {
  is_read?: boolean
  limit?: number
  offset?: number
} = {}): Promise<PaginatedResponse<AlertEvent>> {
  const { data } = await api.get('/alerts/events', { params })
  return data
}

export async function markEventRead(id: string): Promise<void> {
  await api.patch(`/alerts/events/${id}/read`)
}

export async function markAllRead(): Promise<void> {
  await api.post('/alerts/events/read-all')
}

export async function fetchAlertStats(): Promise<AlertStats> {
  const { data } = await api.get('/alerts/stats')
  return data
}
