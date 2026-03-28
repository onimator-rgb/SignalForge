<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { fetchAssets } from '../api/assets'
import { fetchAnomalies, fetchAnomalyStats } from '../api/anomalies'
import { fetchHealth } from '../api/system'
import { generateReport } from '../api/reports'
import { fetchLivePrices, type LivePriceItem } from '../api/live'
import type { AssetListItem, AnomalyEvent, AnomalyStats, HealthResponse } from '../types/api'
import { fmtPrice, timeAgo } from '../utils/format'
import PriceChange from '../components/PriceChange.vue'
import SeverityBadge from '../components/SeverityBadge.vue'
import FreshnessBadge from '../components/FreshnessBadge.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'

const router = useRouter()
const loading = ref(true)
const error = ref('')
const generatingSummary = ref(false)
const topMovers = ref<AssetListItem[]>([])
const recentAnomalies = ref<AnomalyEvent[]>([])
const anomalyStats = ref<AnomalyStats | null>(null)
const health = ref<HealthResponse | null>(null)
const lastRefresh = ref<Date | null>(null)
const livePrices = ref<Map<string, LivePriceItem>>(new Map())
const liveStatus = ref<string>('loading')
let refreshTimer: ReturnType<typeof setInterval>
let liveTimer: ReturnType<typeof setInterval>

async function refreshLive() {
  try {
    const res = await fetchLivePrices()
    const map = new Map<string, LivePriceItem>()
    for (const item of res.items) {
      map.set(item.symbol, item)
    }
    livePrices.value = map
    liveStatus.value = res.live > 0 ? 'live' : 'delayed'
  } catch { /* silent */ }
}

function getLivePrice(symbol: string): LivePriceItem | undefined {
  return livePrices.value.get(symbol)
}

async function loadDashboard() {
  try {
    const [assetsRes, anomaliesRes, statsRes, healthRes] = await Promise.all([
      fetchAssets({ sort_by: 'change_24h', sort_dir: 'desc', limit: 10 }),
      fetchAnomalies({ is_resolved: false, limit: 8 }),
      fetchAnomalyStats(),
      fetchHealth(),
    ])
    topMovers.value = assetsRes.items
    recentAnomalies.value = anomaliesRes.items
    anomalyStats.value = statsRes
    health.value = healthRes
    lastRefresh.value = new Date()
    error.value = ''
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

async function genSummary() {
  generatingSummary.value = true
  try {
    const report = await generateReport({ report_type: 'market_summary' })
    router.push(`/reports/${report.id}`)
  } catch (e: any) {
    alert(e.response?.data?.detail || e.message || 'Failed')
  } finally {
    generatingSummary.value = false
  }
}

onMounted(() => {
  loadDashboard()
  refreshLive()
  refreshTimer = setInterval(loadDashboard, 60_000)
  liveTimer = setInterval(refreshLive, 15_000)
})

onUnmounted(() => {
  clearInterval(refreshTimer)
  clearInterval(liveTimer)
})
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-5">
      <h1 class="text-2xl font-bold">Dashboard</h1>
      <div class="flex items-center gap-3">
        <button
          class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg disabled:opacity-50"
          :disabled="generatingSummary"
          @click="genSummary"
        >{{ generatingSummary ? 'Generowanie...' : 'Market Summary AI' }}</button>
        <FreshnessBadge :status="liveStatus" />
        <span v-if="lastRefresh" class="text-xs text-gray-600">
          {{ lastRefresh.toLocaleTimeString('pl-PL') }}
        </span>
      </div>
    </div>

    <LoadingSpinner v-if="loading" />
    <ErrorBox v-else-if="error" :message="error" />

    <template v-else>
      <!-- Stats row -->
      <div class="grid grid-cols-4 gap-4 mb-6">
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div class="text-xs text-gray-500 uppercase tracking-wide">Status</div>
          <div class="text-lg font-bold mt-1" :class="health?.status === 'ok' ? 'text-green-400' : 'text-red-400'">
            {{ health?.status || '—' }}
          </div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div class="text-xs text-gray-500 uppercase tracking-wide">Anomalie (aktywne)</div>
          <div class="text-lg font-bold mt-1 text-orange-400">{{ anomalyStats?.unresolved ?? 0 }}</div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div class="text-xs text-gray-500 uppercase tracking-wide">Wysokie / Krytyczne</div>
          <div class="text-lg font-bold mt-1 text-red-400">
            {{ (anomalyStats?.by_severity?.high ?? 0) + (anomalyStats?.by_severity?.critical ?? 0) }}
          </div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div class="text-xs text-gray-500 uppercase tracking-wide">Razem wykrytych</div>
          <div class="text-lg font-bold mt-1 text-gray-300">{{ anomalyStats?.total ?? 0 }}</div>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-6">
        <!-- Top movers -->
        <div class="bg-gray-900 border border-gray-800 rounded-lg">
          <div class="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
            <h2 class="font-semibold text-sm">Top Movers (24h)</h2>
            <RouterLink to="/assets" class="text-xs text-blue-400 hover:underline">Wszystkie</RouterLink>
          </div>
          <div v-if="topMovers.length === 0" class="p-8 text-center">
            <div class="text-gray-600 text-2xl mb-2">📈</div>
            <div class="text-sm text-gray-500">Brak danych cenowych.</div>
            <div class="text-xs text-gray-600 mt-1">Uruchom ingestion, aby pobrac dane z Binance.</div>
          </div>
          <table v-else class="w-full text-sm">
            <tbody>
              <tr
                v-for="a in topMovers"
                :key="a.id"
                class="border-b border-gray-800/50 hover:bg-gray-800/30"
              >
                <td class="px-4 py-2.5">
                  <RouterLink :to="`/assets/${a.id}`" class="flex items-center gap-2 hover:text-white">
                    <img v-if="a.image_url" :src="a.image_url" class="w-5 h-5 rounded-full" />
                    <span class="font-medium text-white">{{ a.symbol }}</span>
                    <span class="text-gray-500 text-xs">{{ a.name }}</span>
                  </RouterLink>
                </td>
                <td class="px-4 py-2.5 text-right tabular-nums text-gray-300">
                  ${{ getLivePrice(a.symbol)?.price ? fmtPrice(getLivePrice(a.symbol)!.price!) : (a.latest_price ? fmtPrice(a.latest_price.close) : '—') }}
                </td>
                <td class="px-4 py-2.5 text-right">
                  <PriceChange :value="getLivePrice(a.symbol)?.change_24h_pct ?? a.latest_price?.change_24h_pct" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Recent anomalies -->
        <div class="bg-gray-900 border border-gray-800 rounded-lg">
          <div class="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
            <h2 class="font-semibold text-sm">Ostatnie anomalie</h2>
            <RouterLink to="/anomalies" class="text-xs text-blue-400 hover:underline">Wszystkie</RouterLink>
          </div>
          <div v-if="recentAnomalies.length === 0" class="p-8 text-center">
            <div class="text-gray-600 text-2xl mb-2">✅</div>
            <div class="text-sm text-gray-500">Brak aktywnych anomalii.</div>
            <div class="text-xs text-gray-600 mt-1">System monitoruje rynek — anomalie pojawia sie automatycznie.</div>
          </div>
          <div v-else class="divide-y divide-gray-800/50">
            <RouterLink
              v-for="a in recentAnomalies"
              :key="a.id"
              :to="`/assets/${a.asset_id}`"
              class="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-800/30 text-sm"
            >
              <SeverityBadge :severity="a.severity" />
              <span class="font-medium text-white">{{ a.asset_symbol }}</span>
              <span class="text-gray-400">{{ a.anomaly_type.replace(/_/g, ' ') }}</span>
              <span class="ml-auto text-xs text-gray-500">{{ timeAgo(a.detected_at) }}</span>
            </RouterLink>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
