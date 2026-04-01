<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { fetchPortfolio, triggerEvaluation } from '../api/portfolio'
import { fetchWatchlists, addAssetToWatchlist } from '../api/watchlists'
import type { Watchlist } from '../types/api'
import { fmtPrice, fmtTime, timeAgo } from '../utils/format'
import FreshnessBadge from '../components/FreshnessBadge.vue'
import LastRefreshHint from '../components/LastRefreshHint.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'
import api from '../api/client'
import { useLivePrices } from '../composables/useLivePrices'

const { getPrice, getFreshness, status: liveStatus } = useLivePrices(15_000)

const loading = ref(true)
const error = ref('')
const data = ref<any>(null)
const watchlists = ref<Watchlist[]>([])
const wlMenuForId = ref<string | null>(null)
const evaluating = ref(false)
const closingId = ref<string | null>(null)
const expandedId = ref<string | null>(null)
const protections = ref<any[]>([])
const entryDecisions = ref<any[]>([])

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await fetchPortfolio()
    // Fetch protections
    try {
      const pRes = await api.get('/portfolio/protections')
      protections.value = pRes.data.active || []
    } catch { protections.value = [] }
    try {
      const dRes = await api.get('/portfolio/entry-decisions?limit=10')
      entryDecisions.value = Array.isArray(dRes.data) ? dRes.data : []
    } catch { entryDecisions.value = [] }
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

async function evaluate() {
  evaluating.value = true
  try {
    await triggerEvaluation()
    await load()
  } catch (e: any) {
    alert(e.response?.data?.detail || e.message)
  } finally {
    evaluating.value = false
  }
}

async function closePosition(posId: string) {
  if (!confirm('Zamknac pozycje demo po aktualnej cenie?')) return
  closingId.value = posId
  try {
    await api.post(`/portfolio/positions/${posId}/close`)
    await load()
  } catch (e: any) {
    alert(e.response?.data?.detail || e.message)
  } finally {
    closingId.value = null
  }
}

function toggle(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

onMounted(() => {
  load()
  fetchWatchlists().then(wls => watchlists.value = wls).catch(() => {})
})

async function addToWl(wlId: string, assetId: string) {
  try {
    await addAssetToWatchlist(wlId, assetId)
  } catch { /* silent */ }
  wlMenuForId.value = null
}

// Live price helpers for positions
function liveCurrentPrice(p: any): number {
  return getPrice(p.asset_symbol) ?? p.current_price ?? p.entry_price
}
function liveValue(p: any): number {
  return liveCurrentPrice(p) * p.quantity
}
function liveUnrealizedUsd(p: any): number {
  return +(liveValue(p) - p.entry_value_usd).toFixed(2)
}
function liveUnrealizedPct(p: any): number {
  const entry = p.entry_price
  if (!entry || entry <= 0) return 0
  return +((liveCurrentPrice(p) / entry - 1) * 100).toFixed(2)
}

function pnlClass(val: number | null | undefined): string {
  if (val == null) return 'text-gray-500'
  return val >= 0 ? 'text-green-400' : 'text-red-400'
}

function pnlPrefix(val: number | null | undefined): string {
  if (val == null) return ''
  return val >= 0 ? '+' : ''
}

const badgeColors: Record<string, string> = {
  in_profit: 'text-green-400 bg-green-500/10 border-green-500/30',
  in_loss: 'text-red-400 bg-red-500/10 border-red-500/30',
  near_stop: 'text-red-300 bg-red-500/10 border-red-500/30',
  near_target: 'text-green-300 bg-green-500/10 border-green-500/30',
  expiring_soon: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
}

const reasonLabels: Record<string, string> = {
  stop_hit: 'Stop Loss',
  trailing_stop_hit: 'Trailing Stop',
  target_hit: 'Take Profit',
  break_even_protect: 'Break-Even Protect',
  signal_deterioration: 'Signal Deterioration',
  max_hold: 'Max Hold',
  manual: 'Manual Close',
  signal_invalid: 'Signal Invalid',
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-2">
      <h1 class="text-2xl font-bold">Demo Portfolio</h1>
      <button
        class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg disabled:opacity-50"
        :disabled="evaluating"
        @click="evaluate"
      >{{ evaluating ? 'Evaluating...' : 'Evaluate Now' }}</button>
      <FreshnessBadge :status="liveStatus" />
      <LastRefreshHint />
    </div>
    <div class="text-[10px] text-gray-600 mb-4">Paper trading only — not real money. Results are simulated.</div>

    <LoadingSpinner v-if="loading" />
    <ErrorBox v-else-if="error" :message="error" />

    <template v-else-if="data">
      <!-- Stats -->
      <div class="grid grid-cols-6 gap-3 mb-6">
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-500 uppercase">Equity</div>
          <div class="text-lg font-bold mt-1 tabular-nums">${{ data.stats.equity.toFixed(2) }}</div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-500 uppercase">Return</div>
          <div class="text-lg font-bold mt-1 tabular-nums" :class="pnlClass(data.stats.total_return_pct)">
            {{ pnlPrefix(data.stats.total_return_pct) }}{{ data.stats.total_return_pct.toFixed(2) }}%
          </div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-500 uppercase">Cash</div>
          <div class="text-lg font-bold mt-1 tabular-nums">${{ data.stats.current_cash.toFixed(2) }}</div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-500 uppercase">Unrealized</div>
          <div class="text-lg font-bold mt-1 tabular-nums" :class="pnlClass(data.stats.unrealized_pnl)">
            {{ pnlPrefix(data.stats.unrealized_pnl) }}${{ Math.abs(data.stats.unrealized_pnl).toFixed(2) }}
          </div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-500 uppercase">Positions</div>
          <div class="text-lg font-bold mt-1">{{ data.stats.open_positions }}/5</div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-500 uppercase">Win Rate</div>
          <div class="text-lg font-bold mt-1">{{ data.stats.win_rate != null ? data.stats.win_rate.toFixed(0) + '%' : '--' }}</div>
        </div>
      </div>

      <!-- Entry Decisions -->
      <div v-if="entryDecisions.length > 0" class="mb-5">
        <h2 class="font-semibold text-sm mb-2">Recent Entry Decisions</h2>
        <div class="flex gap-2 flex-wrap">
          <div
            v-for="d in entryDecisions.slice(0, 8)" :key="d.id"
            class="px-2 py-1 rounded text-xs border"
            :class="d.status === 'allowed'
              ? 'bg-green-500/10 border-green-500/30 text-green-400'
              : 'bg-red-500/10 border-red-500/30 text-red-400'"
          >
            <span class="font-medium">{{ d.symbol }}</span>
            <span class="ml-1 opacity-70">{{ d.status === 'allowed' ? 'passed' : (d.reason_codes || []).join(', ') || d.stage }}</span>
          </div>
        </div>
      </div>

      <!-- Active Protections -->
      <div v-if="protections.length > 0" class="mb-5">
        <h2 class="font-semibold text-sm mb-2 text-orange-400">Active Protections ({{ protections.length }})</h2>
        <div class="flex gap-2 flex-wrap">
          <div
            v-for="p in protections" :key="p.id"
            class="px-3 py-1.5 bg-orange-500/10 border border-orange-500/30 rounded-lg text-xs text-orange-400"
          >
            <span class="font-medium">{{ p.type.replace(/_/g, ' ') }}</span>
            <span class="text-orange-300/60 ml-1">{{ p.reason }}</span>
            <span v-if="p.expires_at" class="text-gray-500 ml-1">expires {{ p.expires_at.split('T')[1]?.slice(0,5) || '' }}</span>
          </div>
        </div>
      </div>

      <!-- Open Positions -->
      <h2 class="font-semibold text-sm mb-3">Otwarte pozycje ({{ data.open_positions.length }})</h2>

      <div v-if="data.open_positions.length === 0" class="bg-gray-900 border border-gray-800 rounded-lg p-6 text-center text-sm text-gray-500 mb-6">
        Brak otwartych pozycji. System otworzy pozycje gdy pojawia sie candidate_buy z score >= 65.
      </div>

      <div v-else class="space-y-2 mb-6">
        <div v-for="p in data.open_positions" :key="p.id" class="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <!-- Main row -->
          <div class="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-800/30" @click="toggle(p.id)">
            <RouterLink :to="`/assets/${p.asset_id}`" class="font-medium text-white text-sm hover:text-blue-400 w-16" @click.stop>
              {{ p.asset_symbol }}
            </RouterLink>
            <span class="text-[10px] text-gray-500">{{ p.asset_class }}</span>

            <!-- Badges -->
            <div class="flex gap-1">
              <span
                v-for="b in p.badges" :key="b"
                class="inline-flex px-1.5 py-0.5 rounded text-[9px] font-medium border"
                :class="badgeColors[b] || 'text-gray-400 bg-gray-500/10 border-gray-500/30'"
              >{{ b.replace('_', ' ') }}</span>
            </div>

            <!-- PnL (live overlay) -->
            <div class="ml-auto flex items-center gap-4 text-xs">
              <FreshnessBadge :status="getFreshness(p.asset_symbol)" />
              <span class="text-gray-500">{{ p.hours_open }}h</span>
              <span class="tabular-nums" :class="pnlClass(liveUnrealizedPct(p))">
                {{ pnlPrefix(liveUnrealizedPct(p)) }}{{ liveUnrealizedPct(p).toFixed(2) }}%
              </span>
              <span class="tabular-nums" :class="pnlClass(liveUnrealizedUsd(p))">
                {{ pnlPrefix(liveUnrealizedUsd(p)) }}${{ Math.abs(liveUnrealizedUsd(p)).toFixed(2) }}
              </span>
              <button
                class="px-2 py-0.5 text-[10px] bg-gray-700 hover:bg-gray-600 text-gray-300 rounded disabled:opacity-50"
                :disabled="closingId === p.id"
                @click.stop="closePosition(p.id)"
              >{{ closingId === p.id ? '...' : 'Zamknij' }}</button>
            </div>
          </div>

          <!-- Detail panel -->
          <div v-if="expandedId === p.id" class="border-t border-gray-800 px-4 py-3 bg-gray-950/50">
            <div class="grid grid-cols-5 gap-3 text-xs mb-3">
              <div>
                <div class="text-gray-500">Entry</div>
                <div class="font-medium tabular-nums">${{ fmtPrice(p.entry_price) }}</div>
              </div>
              <div>
                <div class="text-gray-500">Current</div>
                <div class="font-medium tabular-nums">${{ fmtPrice(liveCurrentPrice(p)) }}</div>
              </div>
              <div>
                <div class="text-gray-500">Peak</div>
                <div class="font-medium tabular-nums text-blue-400">{{ p.peak_price ? '$' + fmtPrice(p.peak_price) : '--' }}
                  <span v-if="p.peak_pnl_pct" class="text-gray-600">(+{{ p.peak_pnl_pct.toFixed(1) }}%)</span>
                </div>
              </div>
              <div>
                <div class="text-gray-500">Stop</div>
                <div class="font-medium tabular-nums text-red-400">${{ fmtPrice(p.stop_loss_price) }}</div>
              </div>
              <div>
                <div class="text-gray-500">Target</div>
                <div class="font-medium tabular-nums text-green-400">${{ fmtPrice(p.take_profit_price) }}</div>
              </div>
            </div>
            <div class="flex gap-3 text-xs mb-3">
              <span v-if="p.trailing_stop_price" class="px-2 py-0.5 rounded bg-yellow-500/10 text-yellow-400 border border-yellow-500/30">
                Trail SL: ${{ fmtPrice(p.trailing_stop_price) }}
              </span>
              <span v-if="p.exit_context?.trailing_tp_armed" class="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                Trail TP armed (peak: ${{ fmtPrice(p.exit_context.trailing_tp_peak) }})
              </span>
              <span v-if="p.break_even_armed" class="px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/30">
                BE armed
              </span>
              <span v-if="p.exit_context?.trailing_buy_phase" class="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                Trailing Buy
              </span>
            </div>
            <div class="grid grid-cols-4 gap-4 text-xs mb-3">
              <div>
                <div class="text-gray-500">Qty</div>
                <div class="tabular-nums">{{ p.quantity < 1 ? p.quantity.toFixed(6) : p.quantity.toFixed(2) }}</div>
              </div>
              <div>
                <div class="text-gray-500">Value</div>
                <div class="tabular-nums">${{ liveValue(p).toFixed(2) }}</div>
              </div>
              <div>
                <div class="text-gray-500">Opened</div>
                <div>{{ timeAgo(p.opened_at) }}</div>
              </div>
              <div>
                <div class="text-gray-500">Max hold</div>
                <div>{{ p.hours_remaining > 0 ? p.hours_remaining.toFixed(0) + 'h remaining' : 'expired' }}</div>
              </div>
            </div>

            <!-- Recommendation source -->
            <div v-if="p.recommendation" class="border-t border-gray-800 pt-2 mt-2">
              <div class="text-[10px] text-gray-600 mb-1">Recommendation source</div>
              <div class="flex items-center gap-2 text-xs">
                <span class="text-gray-400">Score: <span class="text-white font-medium">{{ p.recommendation.score?.toFixed(0) }}</span></span>
                <span class="text-gray-400">Type: <span class="text-green-400">{{ p.recommendation.type }}</span></span>
                <span class="text-gray-400">Version: {{ p.recommendation.scoring_version }}</span>
              </div>
              <div v-if="p.recommendation.rationale" class="text-[10px] text-gray-500 mt-1">{{ p.recommendation.rationale }}</div>
            </div>

            <!-- Add to watchlist -->
            <div class="border-t border-gray-800 pt-2 mt-2">
              <div class="relative inline-block">
                <button
                  class="text-xs text-gray-500 hover:text-gray-300"
                  @click.stop="wlMenuForId = wlMenuForId === p.id ? null : p.id"
                >+ Dodaj do watchlisty</button>
                <div
                  v-if="wlMenuForId === p.id && watchlists.length > 0"
                  class="absolute left-0 bottom-6 w-40 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-20 py-1"
                >
                  <button
                    v-for="wl in watchlists" :key="wl.id"
                    class="w-full text-left px-3 py-1 text-xs text-gray-300 hover:bg-gray-700"
                    @click.stop="addToWl(wl.id, p.asset_id)"
                  >{{ wl.name }}</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-6">
        <!-- Closed -->
        <div>
          <h2 class="font-semibold text-sm mb-3">Zamkniete pozycje ({{ data.stats.closed_positions }})</h2>
          <div v-if="data.recent_closed.length === 0" class="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center text-sm text-gray-500">
            Brak zamknietych pozycji.
          </div>
          <div v-else class="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
            <table class="w-full text-xs">
              <thead>
                <tr class="text-gray-500 border-b border-gray-800">
                  <th class="px-3 py-2 text-left">Asset</th>
                  <th class="px-3 py-2 text-right">PnL</th>
                  <th class="px-3 py-2 text-right">Hold</th>
                  <th class="px-3 py-2 text-right">Reason</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in data.recent_closed" :key="p.id" class="border-b border-gray-800/30">
                  <td class="px-3 py-1.5">
                    <RouterLink :to="`/assets/${p.asset_id}`" class="text-white hover:text-blue-400">{{ p.asset_symbol }}</RouterLink>
                    <span class="text-gray-600 text-[10px] ml-1">score {{ p.rec_score?.toFixed(0) || '?' }}</span>
                  </td>
                  <td class="px-3 py-1.5 text-right tabular-nums" :class="pnlClass(p.realized_pnl_pct)">
                    {{ pnlPrefix(p.realized_pnl_pct) }}{{ p.realized_pnl_pct?.toFixed(2) ?? '--' }}%
                  </td>
                  <td class="px-3 py-1.5 text-right text-gray-400">{{ p.hold_hours ? p.hold_hours.toFixed(0) + 'h' : '--' }}</td>
                  <td class="px-3 py-1.5 text-right text-gray-500">{{ reasonLabels[p.close_reason] || p.close_reason || '--' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Transactions -->
        <div>
          <h2 class="font-semibold text-sm mb-3">Ostatnie transakcje</h2>
          <div v-if="data.recent_transactions.length === 0" class="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center text-sm text-gray-500">
            Brak transakcji.
          </div>
          <div v-else class="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
            <table class="w-full text-xs">
              <thead>
                <tr class="text-gray-500 border-b border-gray-800">
                  <th class="px-3 py-2 text-left">Typ</th>
                  <th class="px-3 py-2 text-left">Asset</th>
                  <th class="px-3 py-2 text-right">Value</th>
                  <th class="px-3 py-2 text-right">Czas</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="tx in data.recent_transactions" :key="tx.id" class="border-b border-gray-800/30">
                  <td class="px-3 py-1.5">
                    <span :class="tx.tx_type === 'buy' ? 'text-green-400' : 'text-red-400'">{{ tx.tx_type.toUpperCase() }}</span>
                  </td>
                  <td class="px-3 py-1.5 text-white">{{ tx.asset_symbol }}</td>
                  <td class="px-3 py-1.5 text-right text-gray-300 tabular-nums">${{ tx.value_usd.toFixed(2) }}</td>
                  <td class="px-3 py-1.5 text-right text-gray-500">{{ timeAgo(tx.executed_at) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
