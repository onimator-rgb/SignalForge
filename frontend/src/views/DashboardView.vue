<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { fetchAssets } from '../api/assets'
import { fetchAnomalies } from '../api/anomalies'
import { generateReport } from '../api/reports'
import type { AssetListItem, AnomalyEvent } from '../types/api'
import { fmtPrice, timeAgo } from '../utils/format'
import PriceChange from '../components/PriceChange.vue'
import SeverityBadge from '../components/SeverityBadge.vue'
import FreshnessBadge from '../components/FreshnessBadge.vue'
import LastRefreshHint from '../components/LastRefreshHint.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'
import { useLivePrices } from '../composables/useLivePrices'
import api from '../api/client'

const router = useRouter()
const { getPrice, getChange, status: liveStatus } = useLivePrices(15_000)

const loading = ref(true)
const error = ref('')
const generatingSummary = ref(false)
const strategy = ref<any>(null)
const topMovers = ref<AssetListItem[]>([])
const recentAnomalies = ref<AnomalyEvent[]>([])
const overview = ref<any>(null)
const lastRefresh = ref<Date | null>(null)
let refreshTimer: ReturnType<typeof setInterval>

async function loadDashboard() {
  try {
    const [assetsRes, anomaliesRes, overviewRes, strategyRes] = await Promise.all([
      fetchAssets({ sort_by: 'change_24h', sort_dir: 'desc', limit: 10 }),
      fetchAnomalies({ is_resolved: false, limit: 8 }),
      api.get('/dashboard/overview').then(r => r.data),
      api.get('/strategy/summary').then(r => r.data).catch(() => null),
    ])
    topMovers.value = assetsRes.items
    recentAnomalies.value = anomaliesRes.items
    overview.value = overviewRes
    strategy.value = strategyRes
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
  refreshTimer = setInterval(loadDashboard, 60_000)
})
onUnmounted(() => clearInterval(refreshTimer))

function pnlClass(v: number | null): string {
  if (v == null) return 'text-gray-500'
  return v >= 0 ? 'text-green-400' : 'text-red-400'
}
function pnlPrefix(v: number): string {
  return v >= 0 ? '+' : ''
}

const recTypeColors: Record<string, string> = {
  candidate_buy: 'text-green-400 bg-green-500/10 border-green-500/30',
  watch_only: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  neutral: 'text-gray-400 bg-gray-500/10 border-gray-500/30',
  avoid: 'text-red-400 bg-red-500/10 border-red-500/30',
}
const recLabels: Record<string, string> = {
  candidate_buy: 'BUY', watch_only: 'WATCH', neutral: 'NEUT', avoid: 'AVOID',
}
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
        <template v-if="strategy">
          <span class="inline-flex px-2 py-0.5 rounded text-[10px] font-medium border bg-gray-800 border-gray-700 text-gray-300">
            {{ strategy.profile.name }}
          </span>
          <span
            class="inline-flex px-2 py-0.5 rounded text-[10px] font-medium border"
            :class="{
              'text-green-400 bg-green-500/10 border-green-500/30': strategy.regime.regime === 'risk_on',
              'text-gray-400 bg-gray-500/10 border-gray-500/30': strategy.regime.regime === 'neutral',
              'text-red-400 bg-red-500/10 border-red-500/30': strategy.regime.regime === 'risk_off',
            }"
          >{{ strategy.regime.regime }}</span>
          <span v-if="strategy.auto_switch?.enabled" class="inline-flex px-2 py-0.5 rounded text-[10px] font-medium border text-purple-400 bg-purple-500/10 border-purple-500/30">
            Auto: {{ strategy.auto_switch.recommended_profile }}
          </span>
          <span v-if="strategy.effective" class="inline-flex px-2 py-0.5 rounded text-[10px] font-medium border text-gray-500 bg-gray-800 border-gray-700" :title="strategy.effective.note">
            Threshold: {{ strategy.effective.candidate_buy_threshold }} | Pos: {{ (strategy.effective.max_position_pct * 100).toFixed(0) }}%
          </span>
        </template>
        <FreshnessBadge :status="liveStatus" />
        <LastRefreshHint />
      </div>
    </div>

    <LoadingSpinner v-if="loading" />
    <ErrorBox v-else-if="error" :message="error" />

    <template v-else>
      <!-- Row 1: Key metrics -->
      <div class="grid grid-cols-6 gap-3 mb-5" v-if="overview">
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-500 uppercase">Equity</div>
          <div class="text-lg font-bold mt-1 tabular-nums">${{ overview.portfolio.equity.toFixed(2) }}</div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-500 uppercase">Return</div>
          <div class="text-lg font-bold mt-1 tabular-nums" :class="pnlClass(overview.portfolio.total_return_pct)">
            {{ pnlPrefix(overview.portfolio.total_return_pct) }}{{ overview.portfolio.total_return_pct.toFixed(2) }}%
          </div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-500 uppercase">Buy Signals</div>
          <div class="text-lg font-bold mt-1 text-green-400">{{ overview.signals.counts.candidate_buy || 0 }}</div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-500 uppercase">Positions</div>
          <div class="text-lg font-bold mt-1">{{ overview.portfolio.open_count }}/5</div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-500 uppercase">Anomalies</div>
          <div class="text-lg font-bold mt-1 text-orange-400">{{ overview.alerts.unresolved_anomalies }}</div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-500 uppercase">Unread Alerts</div>
          <div class="text-lg font-bold mt-1" :class="overview.alerts.unread > 0 ? 'text-orange-400' : 'text-gray-400'">
            {{ overview.alerts.unread }}
          </div>
        </div>
      </div>

      <!-- Strategy Profile details -->
      <div v-if="strategy?.profile" class="bg-gray-900 border border-gray-800 rounded-lg p-3 mb-5">
        <div class="flex items-center gap-4 text-xs">
          <span class="text-gray-500 uppercase font-semibold">Strategy</span>
          <span class="tabular-nums">SL: {{ (strategy.profile.stop_loss_pct * 100).toFixed(0) }}%</span>
          <span class="tabular-nums">TP: {{ (strategy.profile.take_profit_pct * 100).toFixed(0) }}%</span>
          <span class="tabular-nums">Trail: {{ (strategy.profile.trailing_pct * 100).toFixed(1) }}%</span>
          <span class="tabular-nums">Trail Arm: {{ (strategy.profile.trailing_arm_pct * 100).toFixed(1) }}%</span>
          <span class="tabular-nums">Trail Buy: {{ (strategy.profile.trailing_buy_bounce_pct * 100).toFixed(1) }}%</span>
          <span v-if="strategy.profile.slippage_buy_pct" class="tabular-nums text-gray-500">Slip: {{ (strategy.profile.slippage_buy_pct * 100).toFixed(2) }}%</span>
          <span class="tabular-nums">Max Hold: {{ strategy.profile.max_hold_hours }}h</span>
          <span class="tabular-nums">Max Pos: {{ (strategy.profile.max_position_pct * 100).toFixed(0) }}%</span>
        </div>
      </div>

      <!-- Row 2: Portfolio positions + Top recommendations -->
      <div class="grid grid-cols-2 gap-5 mb-5" v-if="overview">
        <!-- Portfolio positions -->
        <div class="bg-gray-900 border border-gray-800 rounded-lg">
          <div class="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
            <h2 class="font-semibold text-sm">Portfolio</h2>
            <RouterLink to="/portfolio" class="text-xs text-blue-400 hover:underline">Szczegoly</RouterLink>
          </div>
          <div v-if="overview.portfolio.positions.length === 0" class="p-6 text-center text-sm text-gray-500">
            Brak otwartych pozycji.
          </div>
          <div v-else class="divide-y divide-gray-800/50">
            <RouterLink
              v-for="p in overview.portfolio.positions" :key="p.symbol"
              :to="`/assets/${p.asset_id}`"
              class="flex items-center justify-between px-4 py-2.5 hover:bg-gray-800/30 text-sm"
            >
              <span class="font-medium text-white">{{ p.symbol }}</span>
              <span class="tabular-nums" :class="pnlClass(p.pnl_pct)">
                {{ pnlPrefix(p.pnl_pct) }}{{ p.pnl_pct.toFixed(2) }}%
              </span>
            </RouterLink>
          </div>
        </div>

        <!-- Top recommendations -->
        <div class="bg-gray-900 border border-gray-800 rounded-lg">
          <div class="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
            <h2 class="font-semibold text-sm">Top Signals</h2>
            <RouterLink to="/recommendations" class="text-xs text-blue-400 hover:underline">Wszystkie</RouterLink>
          </div>
          <div v-if="overview.signals.top_recommendations.length === 0" class="p-6 text-center text-sm text-gray-500">
            Brak aktywnych rekomendacji.
          </div>
          <div v-else class="divide-y divide-gray-800/50">
            <RouterLink
              v-for="r in overview.signals.top_recommendations" :key="r.id"
              :to="`/assets/${r.asset_id}`"
              class="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-800/30 text-sm"
            >
              <span class="font-bold tabular-nums w-8" :class="r.score >= 63 ? 'text-green-400' : r.score >= 55 ? 'text-yellow-400' : 'text-gray-400'">{{ r.score.toFixed(0) }}</span>
              <span
                class="inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium border"
                :class="recTypeColors[r.type] || recTypeColors.neutral"
              >{{ recLabels[r.type] || r.type }}</span>
              <span class="text-white font-medium">{{ r.symbol }}</span>
              <span class="text-[10px] text-gray-500">{{ r.asset_class }}</span>
              <span class="ml-auto text-xs text-gray-500">{{ r.confidence }} / {{ r.risk }}</span>
            </RouterLink>
          </div>
        </div>
      </div>

      <!-- Row 3: Top movers + Anomalies -->
      <div class="grid grid-cols-2 gap-5 mb-5">
        <!-- Top movers -->
        <div class="bg-gray-900 border border-gray-800 rounded-lg">
          <div class="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
            <h2 class="font-semibold text-sm">Top Movers (24h)</h2>
            <RouterLink to="/assets" class="text-xs text-blue-400 hover:underline">Wszystkie</RouterLink>
          </div>
          <div v-if="topMovers.length === 0" class="p-6 text-center text-sm text-gray-500">Brak danych.</div>
          <table v-else class="w-full text-sm">
            <tbody>
              <tr v-for="a in topMovers" :key="a.id" class="border-b border-gray-800/50 hover:bg-gray-800/30">
                <td class="px-4 py-2.5">
                  <RouterLink :to="`/assets/${a.id}`" class="flex items-center gap-2 hover:text-white">
                    <img v-if="a.image_url" :src="a.image_url" class="w-5 h-5 rounded-full" />
                    <span class="font-medium text-white">{{ a.symbol }}</span>
                    <span class="text-[10px] text-gray-500">{{ a.asset_class }}</span>
                  </RouterLink>
                </td>
                <td class="px-4 py-2.5 text-right tabular-nums text-gray-300">
                  ${{ getPrice(a.symbol) ? fmtPrice(getPrice(a.symbol)!) : (a.latest_price ? fmtPrice(a.latest_price.close) : '--') }}
                </td>
                <td class="px-4 py-2.5 text-right">
                  <PriceChange :value="getChange(a.symbol) ?? a.latest_price?.change_24h_pct" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Anomalies + alerts -->
        <div class="bg-gray-900 border border-gray-800 rounded-lg">
          <div class="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
            <h2 class="font-semibold text-sm">Anomalie</h2>
            <RouterLink to="/anomalies" class="text-xs text-blue-400 hover:underline">Wszystkie</RouterLink>
          </div>
          <div v-if="recentAnomalies.length === 0" class="p-6 text-center text-sm text-gray-500">Brak aktywnych anomalii.</div>
          <div v-else class="divide-y divide-gray-800/50">
            <RouterLink
              v-for="a in recentAnomalies" :key="a.id"
              :to="`/assets/${a.asset_id}`"
              class="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-800/30 text-sm"
            >
              <SeverityBadge :severity="a.severity" />
              <span class="font-medium text-white">{{ a.asset_symbol }}</span>
              <span class="text-gray-400">{{ a.anomaly_type.replace(/_/g, ' ') }}</span>
              <span v-if="getPrice(a.asset_symbol || '')" class="text-xs tabular-nums text-gray-300 ml-auto mr-2">${{ fmtPrice(getPrice(a.asset_symbol || '')!) }}</span>
              <span class="text-xs text-gray-500" :class="{ 'ml-auto': !getPrice(a.asset_symbol || '') }">{{ timeAgo(a.detected_at) }}</span>
            </RouterLink>
          </div>
        </div>
      </div>

      <!-- Row 4: Watchlists + Signal distribution -->
      <div class="grid grid-cols-2 gap-5" v-if="overview">
        <!-- Watchlists -->
        <div class="bg-gray-900 border border-gray-800 rounded-lg">
          <div class="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
            <h2 class="font-semibold text-sm">Watchlisty</h2>
            <RouterLink to="/watchlists" class="text-xs text-blue-400 hover:underline">Zarzadzaj</RouterLink>
          </div>
          <div v-if="overview.watchlists.length === 0" class="p-6 text-center text-sm text-gray-500">Brak watchlist.</div>
          <div v-else class="divide-y divide-gray-800/50">
            <RouterLink
              v-for="wl in overview.watchlists" :key="wl.id"
              to="/watchlists"
              class="flex items-center justify-between px-4 py-2.5 hover:bg-gray-800/30 text-sm"
            >
              <span class="text-white font-medium">{{ wl.name }}</span>
              <span class="text-xs text-gray-500">{{ wl.asset_count }} assets</span>
            </RouterLink>
          </div>
        </div>

        <!-- Signal distribution -->
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h2 class="font-semibold text-sm mb-3">Signal Distribution</h2>
          <div class="grid grid-cols-4 gap-3">
            <div v-for="(label, type) in { candidate_buy: 'BUY', watch_only: 'WATCH', neutral: 'NEUTRAL', avoid: 'AVOID' }" :key="type" class="text-center">
              <div class="text-2xl font-bold tabular-nums" :class="{
                'text-green-400': type === 'candidate_buy',
                'text-yellow-400': type === 'watch_only',
                'text-gray-400': type === 'neutral',
                'text-red-400': type === 'avoid',
              }">{{ overview.signals.counts[type] || 0 }}</div>
              <div class="text-[10px] text-gray-500 mt-1">{{ label }}</div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
