<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from '../api/client'
import type {
  IngestionStatusResponse,
  IngestionJobOut,
  DiagnosticsSyncItem,
  DiagnosticsError,
} from '../types/api'
import { fmtTime, timeAgo } from '../utils/format'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'

const loading = ref(true)
const error = ref('')

const syncItems = ref<DiagnosticsSyncItem[]>([])
const recentJobs = ref<IngestionJobOut[]>([])
const errors = ref<DiagnosticsError[]>([])

const triggering = ref(false)
const triggerMsg = ref('')
const triggerError = ref(false)

let refreshTimer: ReturnType<typeof setInterval>

const sortedSync = computed(() =>
  [...syncItems.value].sort((a, b) => (b.staleness_seconds ?? 0) - (a.staleness_seconds ?? 0))
)

async function loadAll() {
  error.value = ''
  try {
    const [statusRes, syncRes, errRes] = await Promise.all([
      api.get<IngestionStatusResponse>('/ingestion/status'),
      api.get<DiagnosticsSyncItem[]>('/diagnostics/sync'),
      api.get<DiagnosticsError[]>('/diagnostics/errors', { params: { limit: 20 } }),
    ])
    recentJobs.value = statusRes.data.recent_jobs.slice(0, 10)
    syncItems.value = syncRes.data
    errors.value = errRes.data
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

async function triggerIngestion() {
  triggering.value = true
  triggerMsg.value = ''
  triggerError.value = false
  try {
    await api.post('/ingestion/trigger')
    triggerMsg.value = 'Ingestion triggered successfully'
    triggerError.value = false
    setTimeout(() => loadAll(), 2000)
  } catch (e: any) {
    triggerMsg.value = e.response?.data?.detail || e.message
    triggerError.value = true
  } finally {
    triggering.value = false
    setTimeout(() => { triggerMsg.value = '' }, 5000)
  }
}

function fmtStaleness(seconds: number | null): string {
  if (seconds == null) return '—'
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`
  return `${Math.floor(seconds / 86400)}d`
}

function fmtDuration(ms: number | null): string {
  if (ms == null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

const jobStatusColors: Record<string, string> = {
  completed: 'text-green-400 bg-green-500/10 border-green-500/30',
  failed: 'text-red-400 bg-red-500/10 border-red-500/30',
  running: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
}

onMounted(() => {
  loadAll()
  refreshTimer = setInterval(loadAll, 30_000)
})

onUnmounted(() => clearInterval(refreshTimer))
</script>

<template>
  <div>
    <!-- Header + Trigger -->
    <div class="flex items-center justify-between mb-5">
      <h1 class="text-2xl font-bold text-white">Ingestion Status</h1>
      <div class="flex items-center gap-3">
        <span
          v-if="triggerMsg"
          class="text-sm"
          :class="triggerError ? 'text-red-400' : 'text-green-400'"
        >
          {{ triggerMsg }}
        </span>
        <button
          class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-200 text-sm rounded-lg"
          @click="loadAll"
        >
          Refresh
        </button>
        <button
          class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg disabled:opacity-50 flex items-center gap-2"
          :disabled="triggering"
          @click="triggerIngestion"
        >
          <svg
            v-if="triggering"
            class="animate-spin h-4 w-4"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          {{ triggering ? 'Triggering...' : 'Trigger Ingestion' }}
        </button>
      </div>
    </div>

    <LoadingSpinner v-if="loading" />
    <ErrorBox v-else-if="error" :message="error" />

    <template v-else>
      <!-- Sync Freshness Table -->
      <div class="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden mb-5">
        <div class="px-4 py-3 border-b border-gray-800">
          <h2 class="text-sm font-semibold text-white uppercase tracking-wide">Sync Freshness</h2>
        </div>
        <div v-if="sortedSync.length === 0" class="p-6 text-center text-gray-500 text-sm">
          No sync data available.
        </div>
        <table v-else class="w-full text-sm">
          <thead>
            <tr class="text-xs text-gray-500 uppercase tracking-wide border-b border-gray-800">
              <th class="px-4 py-3 text-left">Asset Symbol</th>
              <th class="px-4 py-3 text-left">Interval</th>
              <th class="px-4 py-3 text-left">Last Bar Time</th>
              <th class="px-4 py-3 text-right">Staleness</th>
              <th class="px-4 py-3 text-center">Status</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in sortedSync"
              :key="s.asset_id + s.interval"
              class="border-b border-gray-800/50"
            >
              <td class="px-4 py-3 text-white font-medium">{{ s.asset_symbol }}</td>
              <td class="px-4 py-3 text-gray-400">{{ s.interval }}</td>
              <td class="px-4 py-3 text-gray-400">
                {{ s.last_bar_time ? timeAgo(s.last_bar_time) : '—' }}
              </td>
              <td class="px-4 py-3 text-right tabular-nums" :class="s.is_stale ? 'text-red-400' : 'text-gray-400'">
                {{ fmtStaleness(s.staleness_seconds) }}
              </td>
              <td class="px-4 py-3 text-center">
                <span
                  class="inline-flex px-2 py-0.5 rounded text-xs font-medium border"
                  :class="s.is_stale
                    ? 'text-red-400 bg-red-500/10 border-red-500/30'
                    : 'text-green-400 bg-green-500/10 border-green-500/30'"
                >
                  {{ s.is_stale ? 'stale' : 'fresh' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Recent Jobs -->
      <div class="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden mb-5">
        <div class="px-4 py-3 border-b border-gray-800">
          <h2 class="text-sm font-semibold text-white uppercase tracking-wide">Recent Jobs</h2>
        </div>
        <div v-if="recentJobs.length === 0" class="p-6 text-center text-gray-500 text-sm">
          No recent jobs.
        </div>
        <table v-else class="w-full text-sm">
          <thead>
            <tr class="text-xs text-gray-500 uppercase tracking-wide border-b border-gray-800">
              <th class="px-4 py-3 text-left">Started</th>
              <th class="px-4 py-3 text-right">Duration</th>
              <th class="px-4 py-3 text-center">Status</th>
              <th class="px-4 py-3 text-right">Assets</th>
              <th class="px-4 py-3 text-right">Bars</th>
              <th class="px-4 py-3 text-right">Errors</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="j in recentJobs"
              :key="j.id"
              class="border-b border-gray-800/50"
            >
              <td class="px-4 py-3 text-gray-400 text-xs">{{ fmtTime(j.started_at) }}</td>
              <td class="px-4 py-3 text-right text-gray-400 tabular-nums">{{ fmtDuration(j.duration_ms) }}</td>
              <td class="px-4 py-3 text-center">
                <span
                  class="inline-flex px-2 py-0.5 rounded text-xs font-medium border"
                  :class="jobStatusColors[j.status] || 'text-gray-400 bg-gray-500/10 border-gray-500/30'"
                >
                  {{ j.status }}
                </span>
              </td>
              <td class="px-4 py-3 text-right text-gray-300 tabular-nums">{{ j.assets_processed }}</td>
              <td class="px-4 py-3 text-right text-gray-300 tabular-nums">{{ j.bars_inserted }}</td>
              <td class="px-4 py-3 text-right tabular-nums" :class="j.errors > 0 ? 'text-red-400' : 'text-gray-400'">
                {{ j.errors }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Error Log -->
      <div class="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        <div class="px-4 py-3 border-b border-gray-800">
          <h2 class="text-sm font-semibold text-white uppercase tracking-wide">Error Log</h2>
        </div>
        <div v-if="errors.length === 0" class="p-6 text-center text-gray-500 text-sm">
          No recent errors.
        </div>
        <table v-else class="w-full text-sm">
          <thead>
            <tr class="text-xs text-gray-500 uppercase tracking-wide border-b border-gray-800">
              <th class="px-4 py-3 text-left">Timestamp</th>
              <th class="px-4 py-3 text-left">Module</th>
              <th class="px-4 py-3 text-left">Message</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(err, idx) in errors"
              :key="idx"
              class="border-b border-gray-800/50"
            >
              <td class="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">{{ fmtTime(err.timestamp) }}</td>
              <td class="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">{{ err.module }}</td>
              <td
                class="px-4 py-3 text-xs"
                :class="err.level === 'error' ? 'text-red-400' : err.level === 'warning' ? 'text-yellow-400' : 'text-gray-400'"
              >
                {{ err.message }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>
