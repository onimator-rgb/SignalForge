<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { fetchAnomalies, fetchAnomalyStats } from '../api/anomalies'
import { generateReport } from '../api/reports'
import type { AnomalyEvent, AnomalyStats } from '../types/api'
import SeverityBadge from '../components/SeverityBadge.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'

const router = useRouter()
const explaining = ref<string | null>(null)  // anomaly ID being explained

const loading = ref(true)
const error = ref('')
const items = ref<AnomalyEvent[]>([])
const total = ref(0)
const stats = ref<AnomalyStats | null>(null)
const page = ref(0)
const pageSize = 30

// Filters
const severity = ref<string>('')
const anomalyType = ref<string>('')
const resolved = ref<string>('false')  // 'true', 'false', '' (all)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params: Record<string, unknown> = {
      limit: pageSize,
      offset: page.value * pageSize,
    }
    if (severity.value) params.severity = severity.value
    if (anomalyType.value) params.anomaly_type = anomalyType.value
    if (resolved.value !== '') params.is_resolved = resolved.value === 'true'

    const [res, statsRes] = await Promise.all([
      fetchAnomalies(params as any),
      stats.value ? Promise.resolve(stats.value) : fetchAnomalyStats(),
    ])
    items.value = res.items
    total.value = res.total
    if (!stats.value) stats.value = statsRes as AnomalyStats
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

onMounted(load)

function applyFilter() {
  page.value = 0
  load()
}

async function explainAnomaly(anomalyId: string) {
  explaining.value = anomalyId
  try {
    const report = await generateReport({ report_type: 'anomaly_explanation', anomaly_event_id: anomalyId })
    router.push(`/reports/${report.id}`)
  } catch (e: any) {
    alert(e.response?.data?.detail || e.message || 'Failed to generate explanation')
  } finally {
    explaining.value = null
  }
}

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleString('pl-PL', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
  })
}
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold mb-5">Anomalie</h1>

    <!-- Stats chips -->
    <div v-if="stats" class="flex gap-3 mb-5 flex-wrap">
      <div class="bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm">
        <span class="text-gray-500">Razem:</span>
        <span class="ml-1 font-medium">{{ stats.total }}</span>
      </div>
      <div class="bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm">
        <span class="text-gray-500">Aktywne:</span>
        <span class="ml-1 font-medium text-orange-400">{{ stats.unresolved }}</span>
      </div>
      <div v-for="(count, sev) in stats.by_severity" :key="sev" class="bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm">
        <SeverityBadge :severity="sev as string" />
        <span class="ml-1.5">{{ count }}</span>
      </div>
    </div>

    <!-- Filters -->
    <div class="flex gap-3 mb-4 flex-wrap">
      <select
        v-model="severity"
        class="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-blue-500"
        @change="applyFilter"
      >
        <option value="">Wszystkie severity</option>
        <option value="critical">Critical</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>

      <select
        v-model="anomalyType"
        class="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-blue-500"
        @change="applyFilter"
      >
        <option value="">Wszystkie typy</option>
        <option value="price_spike">Price spike</option>
        <option value="price_crash">Price crash</option>
        <option value="volume_spike">Volume spike</option>
        <option value="rsi_extreme">RSI extreme</option>
        <option value="squeeze_release">Squeeze release</option>
      </select>

      <select
        v-model="resolved"
        class="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-blue-500"
        @change="applyFilter"
      >
        <option value="">Wszystkie</option>
        <option value="false">Aktywne</option>
        <option value="true">Resolved</option>
      </select>
    </div>

    <LoadingSpinner v-if="loading && items.length === 0" />
    <ErrorBox v-else-if="error" :message="error" />

    <template v-else>
      <div v-if="items.length === 0" class="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center text-gray-500">
        Brak anomalii pasujacych do filtrow.
      </div>

      <div v-else class="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-xs text-gray-500 uppercase tracking-wide border-b border-gray-800">
              <th class="px-4 py-3 text-left">Severity</th>
              <th class="px-4 py-3 text-left">Aktywo</th>
              <th class="px-4 py-3 text-left">Typ</th>
              <th class="px-4 py-3 text-right">Score</th>
              <th class="px-4 py-3 text-left">Szczegoly</th>
              <th class="px-4 py-3 text-right">Wykryto</th>
              <th class="px-4 py-3 text-center">Status</th>
              <th class="px-4 py-3 text-right">AI</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="a in items"
              :key="a.id"
              class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors"
            >
              <td class="px-4 py-3">
                <SeverityBadge :severity="a.severity" />
              </td>
              <td class="px-4 py-3">
                <RouterLink :to="`/assets/${a.asset_id}`" class="text-blue-400 hover:underline font-medium">
                  {{ a.asset_symbol }}
                </RouterLink>
              </td>
              <td class="px-4 py-3" :class="a.anomaly_type === 'squeeze_release' ? 'text-purple-400' : 'text-gray-300'">{{ a.anomaly_type.replace(/_/g, ' ') }}</td>
              <td class="px-4 py-3 text-right tabular-nums text-gray-300">{{ (a.score * 100).toFixed(0) }}%</td>
              <td class="px-4 py-3 text-xs text-gray-500 max-w-48 truncate">
                <template v-if="a.details.z_score">z={{ (a.details.z_score as number).toFixed(2) }}</template>
                <template v-if="a.details.rsi"> RSI={{ (a.details.rsi as number).toFixed(1) }}</template>
                <template v-if="a.details.pct_change"> chg={{ ((a.details.pct_change as number) * 100).toFixed(2) }}%</template>
                <template v-if="a.details.ratio_vs_avg"> vol={{ (a.details.ratio_vs_avg as number).toFixed(1) }}x</template>
                <template v-if="a.details.momentum"> mom={{ ((a.details.momentum as number) * 100).toFixed(2) }}%</template>
                <template v-if="a.details.bb_width"> BB={{ (a.details.bb_width as number).toFixed(4) }}</template>
                <template v-if="a.details.kc_width"> KC={{ (a.details.kc_width as number).toFixed(4) }}</template>
              </td>
              <td class="px-4 py-3 text-right text-xs text-gray-400">{{ fmtTime(a.detected_at) }}</td>
              <td class="px-4 py-3 text-center">
                <span v-if="a.is_resolved" class="text-xs text-gray-500">resolved</span>
                <span v-else class="inline-block w-2 h-2 rounded-full bg-orange-400" title="aktywna" />
              </td>
              <td class="px-4 py-3 text-right">
                <button
                  class="px-2 py-1 text-xs bg-blue-600/20 text-blue-400 border border-blue-500/30 rounded hover:bg-blue-600/40 disabled:opacity-40"
                  :disabled="explaining === a.id"
                  @click.stop="explainAnomaly(a.id)"
                >{{ explaining === a.id ? '...' : 'Wyjasnij' }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div v-if="total > pageSize" class="flex items-center justify-between mt-4 text-sm text-gray-500">
        <span>{{ page * pageSize + 1 }}–{{ Math.min((page + 1) * pageSize, total) }} z {{ total }}</span>
        <div class="flex gap-2">
          <button
            :disabled="page === 0"
            class="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed"
            @click="page--; load()"
          >Wstecz</button>
          <button
            :disabled="(page + 1) * pageSize >= total"
            class="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed"
            @click="page++; load()"
          >Dalej</button>
        </div>
      </div>
    </template>
  </div>
</template>
