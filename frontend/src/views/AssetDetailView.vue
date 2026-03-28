<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { fetchAssetDetail, fetchOHLCV } from '../api/assets'
import { fetchAnomalies } from '../api/anomalies'
import { generateReport } from '../api/reports'
import { fetchWatchlists, addAssetToWatchlist } from '../api/watchlists'
import { fetchAssetRecommendation } from '../api/recommendations'
import type { AssetDetail, PriceBar, AnomalyEvent, Watchlist, Recommendation } from '../types/api'
import { fmtPrice, fmtPriceDetail, fmtVol, fmtTime } from '../utils/format'
import PriceChange from '../components/PriceChange.vue'
import SeverityBadge from '../components/SeverityBadge.vue'
import FreshnessBadge from '../components/FreshnessBadge.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'
import { useLivePrices } from '../composables/useLivePrices'

const { getPrice, getChange, getFreshness } = useLivePrices(15_000)

const route = useRoute()
const router = useRouter()
const assetId = computed(() => route.params.id as string)

const loading = ref(true)
const error = ref('')
const asset = ref<AssetDetail | null>(null)
const bars = ref<PriceBar[]>([])
const anomalies = ref<AnomalyEvent[]>([])
const generatingReport = ref(false)
const interval = ref('1h')
const watchlists = ref<Watchlist[]>([])
const showWatchlistMenu = ref(false)
const watchlistAdding = ref(false)
const recommendation = ref<Recommendation | null>(null)

onMounted(() => {
  loadAll()
  fetchWatchlists().then(wls => watchlists.value = wls).catch(() => {})
  fetchAssetRecommendation(assetId.value).then(r => recommendation.value = r).catch(() => {})
})

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [detail, ohlcv, anomRes] = await Promise.all([
      fetchAssetDetail(assetId.value),
      fetchOHLCV(assetId.value, interval.value, 48),
      fetchAnomalies({ asset_id: assetId.value, limit: 10 }),
    ])
    asset.value = detail
    bars.value = ohlcv.reverse()
    anomalies.value = anomRes.items
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

async function genAssetBrief() {
  generatingReport.value = true
  try {
    const report = await generateReport({ report_type: 'asset_brief', asset_id: assetId.value })
    router.push(`/reports/${report.id}`)
  } catch (e: any) {
    alert(e.response?.data?.detail || e.message || 'Report generation failed')
  } finally {
    generatingReport.value = false
  }
}

async function addToWatchlist(watchlistId: string) {
  watchlistAdding.value = true
  try {
    await addAssetToWatchlist(watchlistId, assetId.value)
    showWatchlistMenu.value = false
  } catch (e: any) {
    const msg = e.response?.data?.detail || e.message
    if (msg.includes('already')) {
      // silently close — already in watchlist
    } else {
      alert(msg)
    }
  } finally {
    watchlistAdding.value = false
    showWatchlistMenu.value = false
  }
}

const sparkData = computed(() => {
  if (bars.value.length === 0) return []
  const closes = bars.value.map(b => b.close)
  const min = Math.min(...closes)
  const max = Math.max(...closes)
  const range = max - min || 1
  return closes.map(c => ((c - min) / range) * 100)
})
</script>

<template>
  <div>
    <RouterLink to="/assets" class="text-sm text-gray-500 hover:text-gray-300 mb-4 inline-block">
      &larr; Aktywa
    </RouterLink>

    <LoadingSpinner v-if="loading" />
    <ErrorBox v-else-if="error" :message="error" />

    <template v-else-if="asset">
      <!-- Header -->
      <div class="flex items-center gap-4 mb-6">
        <img v-if="asset.image_url" :src="asset.image_url" class="w-10 h-10 rounded-full" />
        <div>
          <div class="flex items-center gap-2">
            <h1 class="text-2xl font-bold">{{ asset.symbol }} <span class="text-gray-500 font-normal text-lg">{{ asset.name }}</span></h1>
            <span
              class="inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium border"
              :class="asset.asset_class === 'stock'
                ? 'text-green-400 bg-green-500/10 border-green-500/30'
                : 'text-blue-400 bg-blue-500/10 border-blue-500/30'"
            >{{ asset.asset_class }}</span>
          </div>
          <div class="text-xs text-gray-500">
            <span v-if="asset.market_cap_rank">Rank #{{ asset.market_cap_rank }}</span>
            <span v-if="asset.exchange"> &middot; {{ asset.exchange }}</span>
            <span> &middot; {{ asset.provider_symbol }}</span>
            <span> &middot; {{ asset.currency }}</span>
          </div>
        </div>
        <div class="ml-auto flex items-center gap-4">
          <!-- Watchlist dropdown -->
          <div class="relative">
            <button
              class="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white text-xs rounded-lg"
              @click="showWatchlistMenu = !showWatchlistMenu"
            >+ Watchlista</button>
            <div
              v-if="showWatchlistMenu"
              class="absolute right-0 mt-1 w-48 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-20 py-1"
            >
              <div v-if="watchlists.length === 0" class="px-3 py-2 text-xs text-gray-500">
                Brak watchlist.
                <RouterLink to="/watchlists" class="text-blue-400 hover:underline" @click="showWatchlistMenu = false">Utworz pierwsza</RouterLink>
              </div>
              <button
                v-for="wl in watchlists" :key="wl.id"
                class="w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-700 hover:text-white disabled:opacity-50"
                :disabled="watchlistAdding"
                @click="addToWatchlist(wl.id)"
              >{{ wl.name }} <span class="text-gray-500">({{ wl.asset_count }})</span></button>
            </div>
          </div>
          <button
            class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg disabled:opacity-50"
            :disabled="generatingReport"
            @click="genAssetBrief"
          >
            {{ generatingReport ? 'Generowanie...' : 'Generuj AI Brief' }}
          </button>
          <div class="text-right">
            <div class="text-2xl font-bold tabular-nums">${{ getPrice(asset.symbol) ? fmtPrice(getPrice(asset.symbol)!) : (asset.latest_price ? fmtPrice(asset.latest_price.close) : '—') }}</div>
            <div class="flex items-center gap-2 justify-end">
              <PriceChange :value="getChange(asset.symbol) ?? asset.latest_price?.change_24h_pct" />
              <FreshnessBadge :status="getFreshness(asset.symbol)" />
            </div>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-3 gap-5">
        <!-- Left column: chart + OHLCV table -->
        <div class="col-span-2 space-y-5">
          <!-- Sparkline -->
          <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div class="flex items-center justify-between mb-3">
              <h2 class="text-sm font-semibold">Cena ({{ interval }})</h2>
              <div class="flex gap-1">
                <button
                  v-for="iv in ['1h', '1d']"
                  :key="iv"
                  class="px-2 py-0.5 text-xs rounded"
                  :class="interval === iv ? 'bg-blue-500/20 text-blue-400' : 'text-gray-500 hover:text-gray-300'"
                  @click="interval = iv; loadAll()"
                >{{ iv }}</button>
              </div>
            </div>
            <div v-if="sparkData.length > 0" class="flex items-end gap-px h-24">
              <div
                v-for="(h, i) in sparkData"
                :key="i"
                class="flex-1 rounded-t"
                :class="i === sparkData.length - 1 ? 'bg-blue-400' : 'bg-gray-700'"
                :style="{ height: Math.max(h, 2) + '%' }"
              />
            </div>
            <div v-else class="h-24 flex items-center justify-center text-sm text-gray-600">
              Brak danych dla interwalu {{ interval }}.
            </div>
          </div>

          <!-- OHLCV table -->
          <div class="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
            <div class="px-4 py-3 border-b border-gray-800">
              <h2 class="text-sm font-semibold">Ostatnie dane OHLCV</h2>
            </div>
            <div v-if="bars.length === 0" class="p-6 text-center text-sm text-gray-500">
              Brak danych OHLCV dla interwalu {{ interval }}. Uruchom ingestion.
            </div>
            <div v-else class="max-h-72 overflow-auto">
              <table class="w-full text-xs tabular-nums">
                <thead class="sticky top-0 bg-gray-900">
                  <tr class="text-gray-500 border-b border-gray-800">
                    <th class="px-3 py-2 text-left">Czas</th>
                    <th class="px-3 py-2 text-right">Open</th>
                    <th class="px-3 py-2 text-right">High</th>
                    <th class="px-3 py-2 text-right">Low</th>
                    <th class="px-3 py-2 text-right">Close</th>
                    <th class="px-3 py-2 text-right">Volume</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="b in bars.slice().reverse().slice(0, 24)" :key="b.time" class="border-b border-gray-800/30">
                    <td class="px-3 py-1.5 text-gray-400">{{ fmtTime(b.time) }}</td>
                    <td class="px-3 py-1.5 text-right">{{ fmtPriceDetail(b.open) }}</td>
                    <td class="px-3 py-1.5 text-right text-green-400/70">{{ fmtPriceDetail(b.high) }}</td>
                    <td class="px-3 py-1.5 text-right text-red-400/70">{{ fmtPriceDetail(b.low) }}</td>
                    <td class="px-3 py-1.5 text-right text-white">{{ fmtPriceDetail(b.close) }}</td>
                    <td class="px-3 py-1.5 text-right text-gray-500">{{ fmtVol(b.volume) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- Right column: indicators + anomalies -->
        <div class="space-y-5">
          <!-- Indicators -->
          <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h2 class="text-sm font-semibold mb-3">Wskazniki techniczne</h2>
            <template v-if="asset.indicators">
              <div class="space-y-3 text-sm">
                <div>
                  <div class="flex justify-between">
                    <span class="text-gray-400">RSI (14)</span>
                    <span
                      class="font-medium tabular-nums"
                      :class="{
                        'text-red-400': asset.indicators.rsi_14 != null && asset.indicators.rsi_14 > 70,
                        'text-green-400': asset.indicators.rsi_14 != null && asset.indicators.rsi_14 < 30,
                        'text-gray-200': asset.indicators.rsi_14 != null && asset.indicators.rsi_14 >= 30 && asset.indicators.rsi_14 <= 70,
                      }"
                    >
                      {{ asset.indicators.rsi_14?.toFixed(1) ?? '—' }}
                    </span>
                  </div>
                  <div v-if="asset.indicators.rsi_14 != null" class="mt-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                    <div
                      class="h-full rounded-full"
                      :class="{
                        'bg-red-400': asset.indicators.rsi_14 > 70,
                        'bg-green-400': asset.indicators.rsi_14 < 30,
                        'bg-blue-400': asset.indicators.rsi_14 >= 30 && asset.indicators.rsi_14 <= 70,
                      }"
                      :style="{ width: asset.indicators.rsi_14 + '%' }"
                    />
                  </div>
                </div>

                <div v-if="asset.indicators.macd">
                  <div class="text-gray-400 mb-1">MACD (12,26,9)</div>
                  <div class="grid grid-cols-3 gap-2 text-xs">
                    <div>
                      <div class="text-gray-500">MACD</div>
                      <div class="font-medium tabular-nums">{{ asset.indicators.macd.macd.toFixed(2) }}</div>
                    </div>
                    <div>
                      <div class="text-gray-500">Signal</div>
                      <div class="font-medium tabular-nums">{{ asset.indicators.macd.signal.toFixed(2) }}</div>
                    </div>
                    <div>
                      <div class="text-gray-500">Hist</div>
                      <div class="font-medium tabular-nums" :class="asset.indicators.macd.histogram >= 0 ? 'text-green-400' : 'text-red-400'">
                        {{ asset.indicators.macd.histogram.toFixed(2) }}
                      </div>
                    </div>
                  </div>
                </div>

                <div v-if="asset.indicators.bollinger">
                  <div class="text-gray-400 mb-1">Bollinger (20,2)</div>
                  <div class="grid grid-cols-3 gap-2 text-xs">
                    <div>
                      <div class="text-gray-500">Upper</div>
                      <div class="font-medium tabular-nums">{{ fmtPrice(asset.indicators.bollinger.upper) }}</div>
                    </div>
                    <div>
                      <div class="text-gray-500">Middle</div>
                      <div class="font-medium tabular-nums">{{ fmtPrice(asset.indicators.bollinger.middle) }}</div>
                    </div>
                    <div>
                      <div class="text-gray-500">Lower</div>
                      <div class="font-medium tabular-nums">{{ fmtPrice(asset.indicators.bollinger.lower) }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
            <div v-else class="text-sm text-gray-500">
              Niewystarczajace dane do obliczenia wskaznikow. Potrzeba min. 35 barow.
            </div>
          </div>

          <!-- Anomalies -->
          <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h2 class="text-sm font-semibold mb-3">
              Anomalie
              <span v-if="asset.unresolved_anomalies > 0" class="text-orange-400">({{ asset.unresolved_anomalies }})</span>
            </h2>
            <div v-if="anomalies.length === 0" class="text-sm text-gray-500">Brak wykrytych anomalii.</div>
            <div v-else class="space-y-2">
              <div
                v-for="a in anomalies"
                :key="a.id"
                class="flex items-center gap-2 text-xs"
              >
                <SeverityBadge :severity="a.severity" />
                <span class="text-gray-300">{{ a.anomaly_type.replace(/_/g, ' ') }}</span>
                <span v-if="a.is_resolved" class="text-gray-600 text-[10px]">(resolved)</span>
                <span class="ml-auto text-gray-500">{{ fmtTime(a.detected_at) }}</span>
              </div>
            </div>
          </div>

          <!-- Recommendation -->
          <div v-if="recommendation" class="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h2 class="text-sm font-semibold mb-3">Rekomendacja</h2>
            <div class="flex items-center gap-2 mb-2">
              <span
                class="text-lg font-bold tabular-nums"
                :class="{
                  'text-green-400': recommendation.score >= 70,
                  'text-yellow-400': recommendation.score >= 55 && recommendation.score < 70,
                  'text-gray-400': recommendation.score >= 40 && recommendation.score < 55,
                  'text-red-400': recommendation.score < 40,
                }"
              >{{ recommendation.score.toFixed(0) }}</span>
              <span
                class="inline-flex px-2 py-0.5 rounded text-[10px] font-medium border"
                :class="{
                  'text-green-400 bg-green-500/10 border-green-500/30': recommendation.recommendation_type === 'candidate_buy',
                  'text-yellow-400 bg-yellow-500/10 border-yellow-500/30': recommendation.recommendation_type === 'watch_only',
                  'text-gray-400 bg-gray-500/10 border-gray-500/30': recommendation.recommendation_type === 'neutral',
                  'text-red-400 bg-red-500/10 border-red-500/30': recommendation.recommendation_type === 'avoid',
                }"
              >{{ recommendation.recommendation_type.replace(/_/g, ' ').toUpperCase() }}</span>
            </div>
            <div class="h-1.5 bg-gray-800 rounded-full overflow-hidden mb-3">
              <div
                class="h-full rounded-full"
                :class="{
                  'bg-green-400': recommendation.score >= 70,
                  'bg-yellow-400': recommendation.score >= 55,
                  'bg-gray-500': recommendation.score >= 40,
                  'bg-red-400': recommendation.score < 40,
                }"
                :style="{ width: Math.max(recommendation.score, 2) + '%' }"
              />
            </div>
            <div class="text-xs text-gray-400 mb-2">{{ recommendation.rationale_summary }}</div>
            <div class="flex gap-3 text-xs text-gray-500">
              <span>Conf: <span :class="{ 'text-green-400': recommendation.confidence === 'high', 'text-yellow-400': recommendation.confidence === 'medium' }">{{ recommendation.confidence }}</span></span>
              <span>Risk: <span :class="{ 'text-red-400': recommendation.risk_level === 'high', 'text-yellow-400': recommendation.risk_level === 'medium' }">{{ recommendation.risk_level }}</span></span>
            </div>
            <div class="text-[10px] text-gray-600 mt-2">Technical signal — not investment advice.</div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
