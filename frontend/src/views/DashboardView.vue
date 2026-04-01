<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { fetchAssets } from '../api/assets'
import { fetchAnomalies } from '../api/anomalies'
import { generateReport } from '../api/reports'
import type { AssetListItem, AnomalyEvent, ProtectionsResponse } from '../types/api'
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
const protections = ref<ProtectionsResponse>({ active: [], count: 0 })
const lastRefresh = ref<Date | null>(null)
let refreshTimer: ReturnType<typeof setInterval>

async function loadDashboard() {
  try {
    const [assetsRes, anomaliesRes, overviewRes, strategyRes, protectionsRes] = await Promise.all([
      fetchAssets({ sort_by: 'change_24h', sort_dir: 'desc', limit: 10 }),
      fetchAnomalies({ is_resolved: false, limit: 8 }),
      api.get('/dashboard/overview').then(r => r.data),
      api.get('/strategy/summary').then(r => r.data).catch(() => null),
      api.get('/portfolio/protections').then(r => r.data).catch(() => ({ active: [], count: 0 })),
    ])
    topMovers.value = assetsRes.items
    recentAnomalies.value = anomaliesRes.items
    overview.value = overviewRes
    strategy.value = strategyRes
    protections.value = protectionsRes
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

const aiPanelOpen = ref(false)
const aiTips = computed<string[]>(() => {
  if (!overview.value) return []
  const tips: string[] = []
  if (overview.value.portfolio.total_return_pct < -5)
    tips.push('Portfolio drawdown detected — consider reviewing stop-loss settings')
  if (overview.value.portfolio.open_count === 0)
    tips.push('No open positions — check top buy signals for opportunities')
  if (overview.value.alerts.unresolved_anomalies > 3)
    tips.push('Multiple anomalies active — market may be volatile, proceed with caution')
  if (overview.value.signals.counts.candidate_buy > 3)
    tips.push('Several buy signals available — review recommendations for best entries')
  if (overview.value.portfolio.open_count >= 4)
    tips.push('Near position limit (4/5) — prioritize managing existing positions')
  if (tips.length === 0)
    tips.push('Markets look stable — continue monitoring your watchlist')
  return tips
})

const recTypeColors: Record<string, string> = {
  candidate_buy: 'text-green-400 bg-green-500/10 border-green-500/30',
  watch_only: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  neutral: 'text-gray-400 bg-gray-500/10 border-gray-500/30',
  avoid: 'text-red-400 bg-red-500/10 border-red-500/30',
}
const recLabels: Record<string, string> = {
  candidate_buy: 'BUY', watch_only: 'WATCH', neutral: 'NEUT', avoid: 'AVOID',
}

const protectionTypeColors: Record<string, string> = {
  daily_drawdown: 'text-red-400 bg-red-500/10 border-red-500/30',
  consecutive_sl_guard: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
  stoploss_guard: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
  asset_cooldown: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  class_exposure_cap: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  entry_frequency_cap: 'text-gray-400 bg-gray-500/10 border-gray-500/30',
}

function formatProtectionType(type: string): string {
  return type.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())
}

function expiryMinutes(expiresAt: string): number {
  return Math.max(0, Math.round((new Date(expiresAt).getTime() - Date.now()) / 60000))
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

      <!-- AI Assistant panel -->
      <div class="mb-5 border border-purple-500/30 rounded-lg overflow-hidden" v-if="overview">
        <button
          class="w-full flex items-center justify-between px-4 py-3 bg-purple-500/10 hover:bg-purple-500/15 transition-colors"
          @click="aiPanelOpen = !aiPanelOpen"
        >
          <div class="flex items-center gap-2">
            <span class="text-purple-400">✦</span>
            <span class="font-semibold text-sm text-purple-300">AI Assistant</span>
          </div>
          <span class="text-purple-400 text-xs transition-transform" :class="{ 'rotate-180': aiPanelOpen }">▼</span>
        </button>
        <div v-show="aiPanelOpen" class="bg-gray-900 p-4">
          <div class="grid grid-cols-3 gap-4">
            <!-- Portfolio Insights -->
            <div>
              <h3 class="text-xs text-gray-500 uppercase font-semibold mb-2">Portfolio Insights</h3>
              <div class="space-y-1.5 text-sm">
                <div class="text-gray-300">Equity: <span class="text-white font-medium tabular-nums">${{ overview.portfolio.equity.toFixed(2) }}</span></div>
                <div class="text-gray-300">Return: <span class="font-medium tabular-nums" :class="pnlClass(overview.portfolio.total_return_pct)">{{ pnlPrefix(overview.portfolio.total_return_pct) }}{{ overview.portfolio.total_return_pct.toFixed(2) }}%</span></div>
                <div class="text-gray-300">Positions: <span class="text-white font-medium">{{ overview.portfolio.open_count }}/5</span></div>
              </div>
            </div>
            <!-- Strategy Tips -->
            <div>
              <h3 class="text-xs text-gray-500 uppercase font-semibold mb-2">Strategy Tips</h3>
              <ul class="space-y-1.5 text-sm">
                <li v-for="(tip, i) in aiTips" :key="i" class="flex items-start gap-1.5">
                  <span class="text-yellow-400 mt-0.5">•</span>
                  <span class="text-yellow-400">{{ tip }}</span>
                </li>
              </ul>
            </div>
            <!-- Quick Actions -->
            <div>
              <h3 class="text-xs text-gray-500 uppercase font-semibold mb-2">Quick Actions</h3>
              <div class="space-y-2">
                <button
                  class="w-full px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg disabled:opacity-50"
                  :disabled="generatingSummary"
                  @click="genSummary"
                >{{ generatingSummary ? 'Generowanie...' : 'Market Summary AI' }}</button>
                <RouterLink to="/reports" class="block text-center text-xs text-blue-400 hover:underline">View All Reports</RouterLink>
              </div>
            </div>
          </div>
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

      <!-- Row 4: Watchlists + Signal distribution + Safety -->
      <div class="grid grid-cols-3 gap-5" v-if="overview">
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

        <!-- Safety & Protections -->
        <div class="bg-gray-900 border border-gray-800 rounded-lg">
          <div class="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
            <h2 class="font-semibold text-sm">Safety &amp; Protections</h2>
            <RouterLink to="/portfolio" class="text-xs text-blue-400 hover:underline">Details</RouterLink>
          </div>
          <div class="p-4">
            <!-- Status indicator -->
            <div class="flex items-center gap-2 mb-3">
              <span
                class="inline-block w-2.5 h-2.5 rounded-full"
                :class="{
                  'bg-green-400': protections.count === 0,
                  'bg-yellow-400': protections.count >= 1 && protections.count <= 2,
                  'bg-red-400': protections.count >= 3,
                }"
              ></span>
              <span class="text-sm" :class="{
                'text-green-400': protections.count === 0,
                'text-yellow-400': protections.count >= 1 && protections.count <= 2,
                'text-red-400': protections.count >= 3,
              }">
                <template v-if="protections.count === 0">All Clear</template>
                <template v-else-if="protections.count <= 2">{{ protections.count }} Active</template>
                <template v-else>{{ protections.count }} Active – Trading Restricted</template>
              </span>
            </div>

            <!-- Empty state -->
            <div v-if="protections.active.length === 0" class="text-sm text-gray-500">
              ✓ No active protections – trading unrestricted
            </div>

            <!-- Active protections list -->
            <div v-else class="space-y-2">
              <div v-for="p in protections.active" :key="p.id">
                <span
                  class="inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium border"
                  :class="protectionTypeColors[p.type] || 'text-gray-400 bg-gray-500/10 border-gray-500/30'"
                >{{ formatProtectionType(p.type) }}</span>
                <div class="text-xs text-gray-500 mt-0.5">{{ p.reason }}</div>
                <div v-if="p.expires_at" class="text-xs text-gray-600">Expires: {{ expiryMinutes(p.expires_at) }} min</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
