<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import {
  fetchAlertRules, createAlertRule, deleteAlertRule, updateAlertRule,
  fetchAlertEvents, markEventRead, markAllRead, fetchAlertStats,
} from '../api/alerts'
import { fetchAssets } from '../api/assets'
import { generateReport } from '../api/reports'
import type { AlertRule, AlertEvent, AlertStats, AssetListItem } from '../types/api'
import { fmtTime, timeAgo } from '../utils/format'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'

const router = useRouter()
const loading = ref(true)
const error = ref('')
const rules = ref<AlertRule[]>([])
const events = ref<AlertEvent[]>([])
const eventsTotal = ref(0)
const stats = ref<AlertStats | null>(null)
const assets = ref<AssetListItem[]>([])

// Filters
const filterRead = ref<'unread' | 'all'>('unread')
const filterRuleType = ref('')
const filterAssetId = ref('')

// Form state
const showForm = ref(false)
const formName = ref('')
const formType = ref('price_above')
const formAssetId = ref<string>('')
const formThreshold = ref<number>(0)
const formSeverityMin = ref('high')
const formCooldown = ref(60)
const formSaving = ref(false)

// Report generation per event
const generatingForEvent = ref<Set<string>>(new Set())

const ruleTypes = [
  { value: 'price_above', label: 'Cena powyzej' },
  { value: 'price_below', label: 'Cena ponizej' },
  { value: 'anomaly_detected', label: 'Anomalia wykryta' },
  { value: 'anomaly_severity_min', label: 'Anomalia min. severity' },
]

const ruleTypeLabel = (rt: string) => ruleTypes.find(t => t.value === rt)?.label ?? rt.replace(/_/g, ' ')

const isPriceRule = computed(() => ['price_above', 'price_below'].includes(formType.value))
const isSeverityRule = computed(() => formType.value === 'anomaly_severity_min')

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [rulesRes, statsRes, assetsRes] = await Promise.all([
      fetchAlertRules(),
      fetchAlertStats(),
      fetchAssets({ limit: 50 }),
    ])
    rules.value = rulesRes
    stats.value = statsRes
    assets.value = assetsRes.items
    await loadEvents()
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

async function loadEvents() {
  try {
    const params: Record<string, unknown> = { limit: 50 }
    if (filterRead.value === 'unread') params.is_read = false
    if (filterRuleType.value) params.rule_type = filterRuleType.value
    if (filterAssetId.value) params.asset_id = filterAssetId.value

    const eventsRes = await fetchAlertEvents(params as any)
    events.value = eventsRes.items
    eventsTotal.value = eventsRes.total
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  }
}

watch([filterRead, filterRuleType, filterAssetId], () => loadEvents())

async function submitRule() {
  formSaving.value = true
  try {
    const condition: Record<string, unknown> = {}
    if (isPriceRule.value) condition.threshold = formThreshold.value
    if (isSeverityRule.value) condition.severity_min = formSeverityMin.value

    await createAlertRule({
      name: formName.value,
      rule_type: formType.value,
      condition,
      asset_id: formAssetId.value || null,
      cooldown_minutes: formCooldown.value,
    })
    showForm.value = false
    formName.value = ''
    formThreshold.value = 0
    await loadAll()
  } catch (e: any) {
    alert(e.response?.data?.detail || e.message)
  } finally {
    formSaving.value = false
  }
}

async function toggleRule(rule: AlertRule) {
  await updateAlertRule(rule.id, { is_active: !rule.is_active })
  await loadAll()
}

async function removeRule(id: string) {
  if (!confirm('Usunac regule?')) return
  await deleteAlertRule(id)
  await loadAll()
}

async function markRead(id: string) {
  await markEventRead(id)
  const statsRes = await fetchAlertStats()
  stats.value = statsRes
  await loadEvents()
}

async function markAllEventsRead() {
  await markAllRead()
  const statsRes = await fetchAlertStats()
  stats.value = statsRes
  await loadEvents()
}

function isAnomalyAlert(e: AlertEvent): boolean {
  const rt = e.details?.rule_type as string | undefined
  return rt === 'anomaly_detected' || rt === 'anomaly_severity_min' || !!e.anomaly_event_id
}

async function generateFromAlert(e: AlertEvent) {
  generatingForEvent.value.add(e.id)
  try {
    const isAnomaly = isAnomalyAlert(e)
    const params: Record<string, string> = { alert_event_id: e.id }
    if (isAnomaly && e.anomaly_event_id) {
      params.report_type = 'anomaly_explanation'
      params.anomaly_event_id = e.anomaly_event_id
    } else if (e.asset_id) {
      params.report_type = 'asset_brief'
      params.asset_id = e.asset_id
    } else {
      return
    }
    const report = await generateReport(params)
    router.push(`/reports/${report.id}`)
  } catch (err: any) {
    alert(err.response?.data?.detail || err.message)
  } finally {
    generatingForEvent.value.delete(e.id)
  }
}

function reportButtonLabel(e: AlertEvent): string {
  if (generatingForEvent.value.has(e.id)) return 'Generowanie...'
  return isAnomalyAlert(e) ? 'Wyjasnienie AI' : 'Asset Brief AI'
}

function canGenerateReport(e: AlertEvent): boolean {
  return !!(e.anomaly_event_id || e.asset_id)
}

onMounted(loadAll)
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold mb-5">Alerty</h1>

    <LoadingSpinner v-if="loading" />
    <ErrorBox v-else-if="error" :message="error" />

    <template v-else>
      <!-- Stats -->
      <div class="flex gap-3 mb-5 flex-wrap">
        <div class="bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm">
          <span class="text-gray-500">Reguly:</span>
          <span class="ml-1 font-medium">{{ stats?.active_rules }}/{{ stats?.total_rules }}</span>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm">
          <span class="text-gray-500">Nieprzeczytane:</span>
          <span class="ml-1 font-medium text-orange-400">{{ stats?.unread_events }}</span>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm">
          <span class="text-gray-500">Razem alertow:</span>
          <span class="ml-1 font-medium">{{ stats?.total_events }}</span>
        </div>
      </div>

      <div class="grid grid-cols-5 gap-6">
        <!-- Left: Rules (2 cols) -->
        <div class="col-span-2">
          <div class="flex items-center justify-between mb-3">
            <h2 class="font-semibold text-sm">Reguly alertow</h2>
            <button
              class="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg"
              @click="showForm = !showForm"
            >{{ showForm ? 'Anuluj' : '+ Nowa regula' }}</button>
          </div>

          <!-- Create form -->
          <div v-if="showForm" class="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-3 space-y-3">
            <input v-model="formName" placeholder="Nazwa reguly" class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200" />
            <select v-model="formType" class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200">
              <option v-for="t in ruleTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
            <select v-model="formAssetId" class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200">
              <option value="">Wszystkie aktywa</option>
              <option v-for="a in assets" :key="a.id" :value="a.id">{{ a.symbol }} — {{ a.name }}</option>
            </select>
            <input v-if="isPriceRule" v-model.number="formThreshold" type="number" step="0.01" placeholder="Threshold (np. 100000)" class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200" />
            <select v-if="isSeverityRule" v-model="formSeverityMin" class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200">
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
            <div class="flex items-center gap-2">
              <span class="text-xs text-gray-500">Cooldown (min):</span>
              <input v-model.number="formCooldown" type="number" class="w-20 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200" />
            </div>
            <button
              class="px-4 py-1.5 bg-green-600 hover:bg-green-500 text-white text-sm rounded-lg disabled:opacity-50"
              :disabled="!formName || formSaving"
              @click="submitRule"
            >{{ formSaving ? 'Zapisywanie...' : 'Zapisz' }}</button>
          </div>

          <!-- Rules list -->
          <div v-if="rules.length === 0 && !showForm" class="bg-gray-900 border border-gray-800 rounded-lg p-6 text-center text-sm text-gray-500">
            Brak regul. Stworz pierwsza regule alertu.
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="r in rules" :key="r.id"
              class="bg-gray-900 border border-gray-800 rounded-lg p-3 flex items-center gap-3"
            >
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium text-white truncate">{{ r.name }}</div>
                <div class="text-xs text-gray-500">
                  {{ ruleTypeLabel(r.rule_type) }}
                  <span v-if="r.asset_symbol"> · {{ r.asset_symbol }}</span>
                  <span v-if="r.condition.threshold"> · ${{ r.condition.threshold }}</span>
                  <span v-if="r.condition.severity_min"> · min: {{ r.condition.severity_min }}</span>
                  · cooldown: {{ r.cooldown_minutes }}m
                </div>
              </div>
              <button
                class="text-xs px-2 py-1 rounded border"
                :class="r.is_active ? 'text-green-400 border-green-500/30 bg-green-500/10' : 'text-gray-500 border-gray-700 bg-gray-800'"
                @click="toggleRule(r)"
              >{{ r.is_active ? 'ON' : 'OFF' }}</button>
              <button class="text-xs text-red-400 hover:text-red-300" @click="removeRule(r.id)">Usun</button>
            </div>
          </div>
        </div>

        <!-- Right: Events (3 cols) -->
        <div class="col-span-3">
          <div class="flex items-center justify-between mb-3">
            <h2 class="font-semibold text-sm">
              Zdarzenia
              <span class="text-gray-500 font-normal">({{ eventsTotal }})</span>
            </h2>
            <button
              v-if="stats && stats.unread_events > 0"
              class="text-xs text-blue-400 hover:underline"
              @click="markAllEventsRead"
            >Oznacz wszystkie jako przeczytane</button>
          </div>

          <!-- Filters -->
          <div class="flex gap-2 mb-3 flex-wrap">
            <select
              v-model="filterRead"
              class="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-300"
            >
              <option value="unread">Nieprzeczytane</option>
              <option value="all">Wszystkie</option>
            </select>
            <select
              v-model="filterRuleType"
              class="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-300"
            >
              <option value="">Wszystkie typy</option>
              <option v-for="t in ruleTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
            <select
              v-model="filterAssetId"
              class="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-300"
            >
              <option value="">Wszystkie aktywa</option>
              <option v-for="a in assets" :key="a.id" :value="a.id">{{ a.symbol }}</option>
            </select>
          </div>

          <!-- Events list -->
          <div v-if="events.length === 0" class="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center">
            <div class="text-gray-600 text-2xl mb-2">
              {{ filterRead === 'unread' ? '✅' : '🔔' }}
            </div>
            <div class="text-sm text-gray-500">
              {{ filterRead === 'unread'
                ? 'Brak nieprzeczytanych alertow.'
                : 'Brak alertow pasujacych do filtrow.' }}
            </div>
            <div v-if="filterRead === 'unread'" class="text-xs text-gray-600 mt-1">
              Przelacz na "Wszystkie" aby zobaczyc historie.
            </div>
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="e in events" :key="e.id"
              class="bg-gray-900 border rounded-lg p-3"
              :class="e.is_read ? 'border-gray-800' : 'border-orange-500/30 bg-orange-500/5'"
            >
              <!-- Header row -->
              <div class="flex items-start gap-2">
                <div v-if="!e.is_read" class="w-2 h-2 rounded-full bg-orange-400 mt-1.5 shrink-0" />
                <div class="flex-1 min-w-0">
                  <div class="text-sm text-gray-200">{{ e.message }}</div>
                  <div class="text-xs text-gray-500 mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
                    <span>{{ e.rule_name }}</span>
                    <span class="text-gray-600">{{ ruleTypeLabel((e.details?.rule_type as string) || '') }}</span>
                    <span v-if="e.asset_symbol" class="text-gray-400">{{ e.asset_symbol }}</span>
                    <span>{{ timeAgo(e.triggered_at) }}</span>
                  </div>
                </div>
                <button
                  v-if="!e.is_read"
                  class="text-xs text-gray-500 hover:text-gray-300 shrink-0"
                  @click="markRead(e.id)"
                >Przeczytane</button>
              </div>

              <!-- Actions row -->
              <div class="flex gap-2 mt-2 ml-4">
                <RouterLink
                  v-if="e.asset_id"
                  :to="`/assets/${e.asset_id}`"
                  class="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded
                         bg-gray-800 border border-gray-700 text-gray-300 hover:text-white hover:border-gray-600"
                >
                  <span v-if="e.asset_symbol">{{ e.asset_symbol }}</span>
                  <span v-else>Aktywo</span>
                  <span class="text-gray-600">&rarr;</span>
                </RouterLink>
                <RouterLink
                  v-if="e.anomaly_event_id"
                  to="/anomalies"
                  class="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded
                         bg-gray-800 border border-gray-700 text-gray-300 hover:text-white hover:border-gray-600"
                >
                  Anomalie <span class="text-gray-600">&rarr;</span>
                </RouterLink>
                <button
                  v-if="canGenerateReport(e)"
                  class="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded
                         bg-blue-600/20 border border-blue-500/30 text-blue-400 hover:bg-blue-600/30
                         disabled:opacity-50"
                  :disabled="generatingForEvent.has(e.id)"
                  @click="generateFromAlert(e)"
                >
                  {{ reportButtonLabel(e) }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
