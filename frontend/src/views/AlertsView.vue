<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { RouterLink } from 'vue-router'
import {
  fetchAlertRules, createAlertRule, deleteAlertRule, updateAlertRule,
  fetchAlertEvents, markEventRead, markAllRead, fetchAlertStats,
} from '../api/alerts'
import { fetchAssets } from '../api/assets'
import type { AlertRule, AlertEvent, AlertStats, AssetListItem } from '../types/api'
import { fmtTime } from '../utils/format'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'

const loading = ref(true)
const error = ref('')
const rules = ref<AlertRule[]>([])
const events = ref<AlertEvent[]>([])
const eventsTotal = ref(0)
const stats = ref<AlertStats | null>(null)
const assets = ref<AssetListItem[]>([])

// Form state
const showForm = ref(false)
const formName = ref('')
const formType = ref('price_above')
const formAssetId = ref<string>('')
const formThreshold = ref<number>(0)
const formSeverityMin = ref('high')
const formCooldown = ref(60)
const formSaving = ref(false)

const ruleTypes = [
  { value: 'price_above', label: 'Cena powyzej' },
  { value: 'price_below', label: 'Cena ponizej' },
  { value: 'anomaly_detected', label: 'Anomalia wykryta' },
  { value: 'anomaly_severity_min', label: 'Anomalia min. severity' },
]

const isPriceRule = computed(() => ['price_above', 'price_below'].includes(formType.value))
const isSeverityRule = computed(() => formType.value === 'anomaly_severity_min')

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [rulesRes, eventsRes, statsRes, assetsRes] = await Promise.all([
      fetchAlertRules(),
      fetchAlertEvents({ limit: 30 }),
      fetchAlertStats(),
      fetchAssets({ limit: 50 }),
    ])
    rules.value = rulesRes
    events.value = eventsRes.items
    eventsTotal.value = eventsRes.total
    stats.value = statsRes
    assets.value = assetsRes.items
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

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
  await loadAll()
}

async function markAllEventsRead() {
  await markAllRead()
  await loadAll()
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

      <div class="grid grid-cols-2 gap-6">
        <!-- Left: Rules -->
        <div>
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
                  {{ r.rule_type.replace(/_/g, ' ') }}
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

        <!-- Right: Events -->
        <div>
          <div class="flex items-center justify-between mb-3">
            <h2 class="font-semibold text-sm">Ostatnie alerty</h2>
            <button
              v-if="stats && stats.unread_events > 0"
              class="text-xs text-blue-400 hover:underline"
              @click="markAllEventsRead"
            >Oznacz wszystkie jako przeczytane</button>
          </div>

          <div v-if="events.length === 0" class="bg-gray-900 border border-gray-800 rounded-lg p-6 text-center text-sm text-gray-500">
            Brak alertow. Alerty pojawia sie automatycznie.
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="e in events" :key="e.id"
              class="bg-gray-900 border rounded-lg p-3 flex items-start gap-3"
              :class="e.is_read ? 'border-gray-800' : 'border-orange-500/30 bg-orange-500/5'"
            >
              <div v-if="!e.is_read" class="w-2 h-2 rounded-full bg-orange-400 mt-1.5 shrink-0" />
              <div class="flex-1 min-w-0">
                <div class="text-sm text-gray-200">{{ e.message }}</div>
                <div class="text-xs text-gray-500 mt-1">
                  <span v-if="e.asset_symbol">
                    <RouterLink :to="`/assets/${e.asset_id}`" class="text-blue-400 hover:underline">{{ e.asset_symbol }}</RouterLink> ·
                  </span>
                  {{ e.rule_name }} · {{ fmtTime(e.triggered_at) }}
                </div>
              </div>
              <button
                v-if="!e.is_read"
                class="text-xs text-gray-500 hover:text-gray-300 shrink-0"
                @click="markRead(e.id)"
              >Przeczytane</button>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
