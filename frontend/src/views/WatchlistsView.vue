<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import {
  fetchWatchlists, createWatchlist, deleteWatchlist,
  fetchWatchlistAssets, removeAssetFromWatchlist,
  fetchWatchlistIntelligence, fetchWatchlistRecommendations,
} from '../api/watchlists'
import { generateReport } from '../api/reports'
import type { Watchlist, WatchlistAsset } from '../types/api'
import { fmtPrice } from '../utils/format'
import PriceChange from '../components/PriceChange.vue'
import FreshnessBadge from '../components/FreshnessBadge.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'
import { useLivePrices } from '../composables/useLivePrices'

const router = useRouter()
const { getPrice, getChange, getFreshness } = useLivePrices(20_000)

const loading = ref(true)
const error = ref('')
const watchlists = ref<Watchlist[]>([])

const showForm = ref(false)
const formName = ref('')
const formDesc = ref('')
const formSaving = ref(false)

const selectedId = ref<string | null>(null)
const selectedAssets = ref<WatchlistAsset[]>([])
const assetsLoading = ref(false)
const intel = ref<any>(null)
const recs = ref<any[]>([])
const generatingSummary = ref(false)

const classColors: Record<string, string> = {
  crypto: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  stock: 'text-green-400 bg-green-500/10 border-green-500/30',
}
const recColors: Record<string, string> = {
  candidate_buy: 'text-green-400',
  watch_only: 'text-yellow-400',
  neutral: 'text-gray-500',
  avoid: 'text-red-400',
}

async function loadWatchlists() {
  loading.value = true
  error.value = ''
  try {
    watchlists.value = await fetchWatchlists()
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

async function submitCreate() {
  if (!formName.value.trim()) return
  formSaving.value = true
  try {
    const wl = await createWatchlist({ name: formName.value.trim(), description: formDesc.value.trim() || undefined })
    showForm.value = false
    formName.value = ''
    formDesc.value = ''
    await loadWatchlists()
    selectWatchlist(wl.id)
  } catch (e: any) { alert(e.response?.data?.detail || e.message) }
  finally { formSaving.value = false }
}

async function removeWatchlist(id: string) {
  if (!confirm('Usunac watchliste?')) return
  await deleteWatchlist(id)
  if (selectedId.value === id) { selectedId.value = null; selectedAssets.value = []; intel.value = null; recs.value = [] }
  await loadWatchlists()
}

async function selectWatchlist(id: string) {
  selectedId.value = id
  assetsLoading.value = true
  try {
    const [assets, intelligence, recommendations] = await Promise.all([
      fetchWatchlistAssets(id),
      fetchWatchlistIntelligence(id),
      fetchWatchlistRecommendations(id),
    ])
    selectedAssets.value = assets
    intel.value = intelligence
    recs.value = recommendations
  } catch (e: any) { error.value = e.response?.data?.detail || e.message }
  finally { assetsLoading.value = false }
}

async function removeAsset(assetId: string) {
  if (!selectedId.value) return
  await removeAssetFromWatchlist(selectedId.value, assetId)
  selectedAssets.value = selectedAssets.value.filter(a => a.asset_id !== assetId)
  const wl = watchlists.value.find(w => w.id === selectedId.value)
  if (wl) wl.asset_count--
}

async function genSummary() {
  if (!selectedId.value) return
  generatingSummary.value = true
  try {
    const report = await generateReport({ report_type: 'watchlist_summary', watchlist_id: selectedId.value })
    router.push(`/reports/${report.id}`)
  } catch (e: any) { alert(e.response?.data?.detail || e.message) }
  finally { generatingSummary.value = false }
}

const selectedWatchlist = () => watchlists.value.find(w => w.id === selectedId.value)

onMounted(loadWatchlists)
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold mb-5">Watchlisty</h1>

    <LoadingSpinner v-if="loading" />
    <ErrorBox v-else-if="error" :message="error" />

    <template v-else>
      <div class="grid grid-cols-5 gap-6">
        <!-- Left: Watchlists (2 cols) -->
        <div class="col-span-2">
          <div class="flex items-center justify-between mb-3">
            <h2 class="font-semibold text-sm">Twoje watchlisty</h2>
            <button class="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg" @click="showForm = !showForm">
              {{ showForm ? 'Anuluj' : '+ Nowa' }}
            </button>
          </div>

          <div v-if="showForm" class="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-3 space-y-3">
            <input v-model="formName" placeholder="Nazwa watchlisty" class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200" />
            <input v-model="formDesc" placeholder="Opis (opcjonalnie)" class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200" />
            <button class="px-4 py-1.5 bg-green-600 hover:bg-green-500 text-white text-sm rounded-lg disabled:opacity-50" :disabled="!formName.trim() || formSaving" @click="submitCreate">
              {{ formSaving ? 'Tworzenie...' : 'Utworz' }}
            </button>
          </div>

          <div v-if="watchlists.length === 0 && !showForm" class="bg-gray-900 border border-gray-800 rounded-lg p-6 text-center text-sm text-gray-500">
            Brak watchlist. Utworz pierwsza.
          </div>
          <div v-else class="space-y-2">
            <div v-for="wl in watchlists" :key="wl.id"
              class="bg-gray-900 border rounded-lg p-3 flex items-center gap-3 cursor-pointer transition-colors"
              :class="selectedId === wl.id ? 'border-blue-500/40 bg-blue-500/5' : 'border-gray-800 hover:border-gray-700'"
              @click="selectWatchlist(wl.id)">
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium text-white truncate">{{ wl.name }}</div>
                <div class="text-xs text-gray-500">{{ wl.asset_count }} aktywow</div>
              </div>
              <button class="text-xs text-red-400 hover:text-red-300 shrink-0" @click.stop="removeWatchlist(wl.id)">Usun</button>
            </div>
          </div>
        </div>

        <!-- Right: Detail (3 cols) -->
        <div class="col-span-3">
          <template v-if="selectedId">
            <LoadingSpinner v-if="assetsLoading" />
            <template v-else>
              <!-- Intelligence strip -->
              <div v-if="intel" class="flex gap-3 mb-4 flex-wrap">
                <div class="bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm">
                  <span class="text-gray-500">Assets:</span> <span class="font-medium">{{ intel.total_assets }}</span>
                  <span class="text-gray-600 text-xs ml-1">({{ intel.crypto_count }}c / {{ intel.stock_count }}s)</span>
                </div>
                <div class="bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm">
                  <span class="text-gray-500">Buy signals:</span> <span class="font-medium text-green-400">{{ intel.candidate_buy_count }}</span>
                </div>
                <div class="bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm">
                  <span class="text-gray-500">Positions:</span> <span class="font-medium">{{ intel.open_positions }}</span>
                </div>
                <div class="bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm">
                  <span class="text-gray-500">Anomalies:</span> <span class="font-medium text-orange-400">{{ intel.unresolved_anomalies }}</span>
                </div>
                <button
                  class="px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg disabled:opacity-50"
                  :disabled="generatingSummary"
                  @click="genSummary"
                >{{ generatingSummary ? 'Generowanie...' : 'AI Summary' }}</button>
              </div>

              <!-- Recommendations for this watchlist -->
              <div v-if="recs.length > 0" class="mb-4">
                <h3 class="text-xs font-semibold text-gray-400 uppercase mb-2">Signals</h3>
                <div class="flex gap-2 flex-wrap">
                  <RouterLink
                    v-for="r in recs" :key="r.id"
                    :to="`/assets/${r.asset_id}`"
                    class="inline-flex items-center gap-1.5 px-2 py-1 bg-gray-900 border border-gray-800 rounded text-xs hover:border-gray-600"
                  >
                    <span class="font-medium text-white">{{ r.symbol }}</span>
                    <span :class="recColors[r.recommendation_type] || 'text-gray-500'">{{ r.score.toFixed(0) }}</span>
                    <span class="text-gray-600">{{ r.recommendation_type === 'candidate_buy' ? 'BUY' : r.recommendation_type === 'watch_only' ? 'WATCH' : r.recommendation_type === 'avoid' ? 'AVOID' : '--' }}</span>
                  </RouterLink>
                </div>
              </div>

              <!-- Assets table -->
              <div v-if="selectedAssets.length === 0" class="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center">
                <div class="text-sm text-gray-500">Watchlista jest pusta.</div>
              </div>
              <div v-else class="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
                <table class="w-full text-sm">
                  <thead>
                    <tr class="text-xs text-gray-500 uppercase tracking-wide border-b border-gray-800">
                      <th class="px-4 py-3 text-left">Aktywo</th>
                      <th class="px-4 py-3 text-center">Typ</th>
                      <th class="px-4 py-3 text-right">Cena</th>
                      <th class="px-4 py-3 text-right">24h</th>
                      <th class="px-4 py-3 text-center">Signal</th>
                      <th class="px-4 py-3 text-center">Status</th>
                      <th class="px-4 py-3 text-right"></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="a in selectedAssets" :key="a.asset_id" class="border-b border-gray-800/50 hover:bg-gray-800/30">
                      <td class="px-4 py-3">
                        <RouterLink :to="`/assets/${a.asset_id}`" class="flex items-center gap-2.5 hover:text-white">
                          <img v-if="a.image_url" :src="a.image_url" class="w-5 h-5 rounded-full" />
                          <div>
                            <div class="font-medium text-white">{{ a.symbol }}</div>
                            <div class="text-xs text-gray-500">{{ a.name }}</div>
                          </div>
                        </RouterLink>
                      </td>
                      <td class="px-4 py-3 text-center">
                        <span class="inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium border" :class="classColors[a.asset_class] || classColors.crypto">{{ a.asset_class }}</span>
                      </td>
                      <td class="px-4 py-3 text-right tabular-nums text-gray-300">
                        {{ getPrice(a.symbol) ? '$' + fmtPrice(getPrice(a.symbol)!) : (a.latest_price ? '$' + fmtPrice(a.latest_price) : '--') }}
                      </td>
                      <td class="px-4 py-3 text-right"><PriceChange :value="getChange(a.symbol) ?? a.change_24h_pct" /></td>
                      <td class="px-4 py-3 text-center">
                        <span v-if="a.rec_type" class="text-xs" :class="recColors[a.rec_type] || 'text-gray-500'">
                          {{ a.rec_type === 'candidate_buy' ? 'BUY' : a.rec_type === 'watch_only' ? 'WATCH' : a.rec_type === 'avoid' ? 'AVOID' : '--' }}
                          <span v-if="a.rec_score" class="text-gray-600 ml-0.5">{{ a.rec_score.toFixed(0) }}</span>
                        </span>
                        <span v-else class="text-xs text-gray-600">--</span>
                      </td>
                      <td class="px-4 py-3 text-center">
                        <span v-if="a.in_portfolio" class="inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium border text-purple-400 bg-purple-500/10 border-purple-500/30 mr-1">OPEN</span>
                        <FreshnessBadge :status="getFreshness(a.symbol)" />
                      </td>
                      <td class="px-4 py-3 text-right">
                        <button class="text-xs text-red-400 hover:text-red-300" @click="removeAsset(a.asset_id)">Usun</button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </template>
          </template>
          <div v-else class="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center">
            <div class="text-gray-600 text-2xl mb-2">👈</div>
            <div class="text-sm text-gray-500">Wybierz watchliste z listy po lewej.</div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
