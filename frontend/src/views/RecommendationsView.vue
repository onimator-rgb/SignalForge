<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { fetchActiveRecommendations } from '../api/recommendations'
import { fetchWatchlists, addAssetToWatchlist } from '../api/watchlists'
import type { Recommendation, Watchlist } from '../types/api'
import { fmtPrice, fmtTime } from '../utils/format'
import FreshnessBadge from '../components/FreshnessBadge.vue'
import PriceDelta from '../components/PriceDelta.vue'
import LastRefreshHint from '../components/LastRefreshHint.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'
import { useLivePrices } from '../composables/useLivePrices'

const { getPrice, getFreshness, status: liveStatus } = useLivePrices(15_000)

const loading = ref(true)
const error = ref('')
const recs = ref<Recommendation[]>([])
const filterClass = ref('')
const expandedId = ref<string | null>(null)
const watchlists = ref<Watchlist[]>([])
const wlMenuForId = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params: Record<string, unknown> = {}
    if (filterClass.value) params.asset_class = filterClass.value
    recs.value = await fetchActiveRecommendations(params as any)
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  fetchWatchlists().then(wls => watchlists.value = wls).catch(() => {})
})
watch(filterClass, load)

async function addToWl(wlId: string, assetId: string) {
  try {
    await addAssetToWatchlist(wlId, assetId)
  } catch { /* duplicate or error — silently close */ }
  wlMenuForId.value = null
}

function toggle(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

const typeColors: Record<string, string> = {
  candidate_buy: 'text-green-400 bg-green-500/10 border-green-500/30',
  watch_only: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  neutral: 'text-gray-400 bg-gray-500/10 border-gray-500/30',
  avoid: 'text-red-400 bg-red-500/10 border-red-500/30',
}

const typeLabels: Record<string, string> = {
  candidate_buy: 'BUY signal',
  watch_only: 'WATCH',
  neutral: 'NEUTRAL',
  avoid: 'AVOID',
}

const confColors: Record<string, string> = {
  high: 'text-green-400',
  medium: 'text-yellow-400',
  low: 'text-gray-500',
}

const riskColors: Record<string, string> = {
  low: 'text-green-400',
  medium: 'text-yellow-400',
  high: 'text-red-400',
}

const classColors: Record<string, string> = {
  crypto: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  stock: 'text-green-400 bg-green-500/10 border-green-500/30',
}

function scoreColor(score: number): string {
  if (score >= 70) return 'text-green-400'
  if (score >= 55) return 'text-yellow-400'
  if (score >= 40) return 'text-gray-400'
  return 'text-red-400'
}

function scoreBarWidth(score: number): string {
  return Math.max(score, 2) + '%'
}

function scoreBarColor(score: number): string {
  if (score >= 70) return 'bg-green-400'
  if (score >= 55) return 'bg-yellow-400'
  if (score >= 40) return 'bg-gray-500'
  return 'bg-red-400'
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-2">
      <div class="flex items-center gap-3">
        <h1 class="text-2xl font-bold">Rekomendacje</h1>
        <FreshnessBadge :status="liveStatus" />
        <LastRefreshHint />
      </div>
      <div class="flex gap-1">
        <button
          v-for="opt in [{ value: '', label: 'Wszystkie' }, { value: 'crypto', label: 'Crypto' }, { value: 'stock', label: 'Stocks' }]"
          :key="opt.value"
          class="px-3 py-1 text-xs rounded-lg border transition-colors"
          :class="filterClass === opt.value
            ? 'bg-blue-600/20 border-blue-500/40 text-blue-400'
            : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-gray-200'"
          @click="filterClass = opt.value"
        >{{ opt.label }}</button>
      </div>
    </div>

    <!-- Disclaimer -->
    <div class="text-[10px] text-gray-600 mb-4 leading-tight">
      Technical signals only — not investment advice. Based on historical data analysis.
      Past performance does not guarantee future results.
    </div>

    <LoadingSpinner v-if="loading" />
    <ErrorBox v-else-if="error" :message="error" />

    <template v-else>
      <div v-if="recs.length === 0" class="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center">
        <div class="text-gray-600 text-2xl mb-2">📡</div>
        <div class="text-sm text-gray-500">Brak aktywnych rekomendacji. Uruchom ingestion, aby wygenerowac sygnaly.</div>
      </div>

      <div v-else class="space-y-2">
        <div
          v-for="r in recs" :key="r.id"
          class="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden"
        >
          <!-- Row -->
          <div
            class="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-800/30 transition-colors"
            @click="toggle(r.id)"
          >
            <!-- Score bar -->
            <div class="w-12 text-right">
              <div class="text-sm font-bold tabular-nums" :class="scoreColor(r.score)">{{ r.score.toFixed(0) }}</div>
            </div>

            <!-- Score visual -->
            <div class="w-20 h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <div class="h-full rounded-full" :class="scoreBarColor(r.score)" :style="{ width: scoreBarWidth(r.score) }" />
            </div>

            <!-- Type badge -->
            <span
              class="inline-flex px-2 py-0.5 rounded text-[10px] font-medium border shrink-0"
              :class="typeColors[r.recommendation_type] || typeColors.neutral"
            >{{ typeLabels[r.recommendation_type] || r.recommendation_type }}</span>

            <!-- Asset -->
            <RouterLink
              :to="`/assets/${r.asset_id}`"
              class="font-medium text-white hover:text-blue-400 text-sm"
              @click.stop
            >{{ r.asset_symbol }}</RouterLink>

            <!-- Class badge -->
            <span
              class="inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium border"
              :class="classColors[r.asset_class || 'crypto']"
            >{{ r.asset_class }}</span>

            <!-- Live price + delta + Confidence + Risk -->
            <div class="ml-auto flex items-center gap-3 text-xs">
              <span v-if="getPrice(r.asset_symbol || '')" class="tabular-nums text-gray-300">${{ fmtPrice(getPrice(r.asset_symbol || '')!) }}</span>
              <PriceDelta :entry-price="r.entry_price_snapshot" :current-price="getPrice(r.asset_symbol || '')" />
              <FreshnessBadge :status="getFreshness(r.asset_symbol || '')" />
              <span :class="confColors[r.confidence]">{{ r.confidence }}</span>
              <span :class="riskColors[r.risk_level]">{{ r.risk_level }}</span>
            </div>
          </div>

          <!-- Expanded detail -->
          <div v-if="expandedId === r.id" class="border-t border-gray-800 px-4 py-3 bg-gray-950/50">
            <div class="text-sm text-gray-300 mb-3">{{ r.rationale_summary }}</div>

            <div class="grid grid-cols-4 gap-3 text-xs mb-3">
              <div v-for="(sig, name) in r.signal_breakdown" :key="name" class="bg-gray-900 border border-gray-800 rounded p-2">
                <div class="text-gray-500 mb-1">{{ name }}</div>
                <div class="font-medium tabular-nums" :class="sig.score > 0.1 ? 'text-green-400' : sig.score < -0.1 ? 'text-red-400' : 'text-gray-400'">
                  {{ sig.score > 0 ? '+' : '' }}{{ sig.score.toFixed(2) }}
                </div>
                <div class="text-gray-600 text-[10px] mt-0.5">{{ sig.detail }}</div>
              </div>
            </div>

            <div class="flex gap-4 text-xs text-gray-500 flex-wrap">
              <span>Entry: ${{ r.entry_price_snapshot ? fmtPrice(r.entry_price_snapshot) : '—' }}</span>
              <span v-if="getPrice(r.asset_symbol || '')">Now: ${{ fmtPrice(getPrice(r.asset_symbol || '')!) }}
                <PriceDelta :entry-price="r.entry_price_snapshot" :current-price="getPrice(r.asset_symbol || '')" />
              </span>
              <span>Horizon: {{ r.time_horizon }}</span>
              <span>Valid: {{ r.valid_until ? fmtTime(r.valid_until) : '—' }}</span>
              <span>Generated: {{ fmtTime(r.generated_at) }}</span>
              <!-- Add to watchlist -->
              <div class="relative ml-auto">
                <button
                  class="text-xs text-gray-500 hover:text-gray-300"
                  @click.stop="wlMenuForId = wlMenuForId === r.id ? null : r.id"
                >+ Watchlista</button>
                <div
                  v-if="wlMenuForId === r.id && watchlists.length > 0"
                  class="absolute right-0 bottom-6 w-40 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-20 py-1"
                >
                  <button
                    v-for="wl in watchlists" :key="wl.id"
                    class="w-full text-left px-3 py-1 text-xs text-gray-300 hover:bg-gray-700"
                    @click.stop="addToWl(wl.id, r.asset_id)"
                  >{{ wl.name }}</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
