<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
  fetchLeaderboard,
  fetchTraders,
  triggerEvaluation,
  triggerCheckExits,
  triggerSnapshots,
  type LeaderboardEntry,
  type Trader,
} from '../api/arena'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'

const leaderboard = ref<LeaderboardEntry[]>([])
const traders = ref<Trader[]>([])
const loading = ref(true)
const error = ref('')
const evaluating = ref(false)
const evalResult = ref<any>(null)

const totalValue = computed(() => leaderboard.value.reduce((s, e) => s + e.portfolio_value_usd, 0))
const totalTrades = computed(() => leaderboard.value.reduce((s, e) => s + e.total_trades, 0))
const bestTrader = computed(() => leaderboard.value[0] || null)
const worstTrader = computed(() => leaderboard.value[leaderboard.value.length - 1] || null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [lb, tl] = await Promise.all([fetchLeaderboard(), fetchTraders()])
    leaderboard.value = lb
    traders.value = tl
  } catch (e: any) {
    error.value = e.message || 'Failed to load arena data'
  } finally {
    loading.value = false
  }
}

async function runEvaluation() {
  evaluating.value = true
  evalResult.value = null
  try {
    await triggerCheckExits()
    const result = await triggerEvaluation()
    evalResult.value = result
    await triggerSnapshots()
    await load()
  } catch (e: any) {
    error.value = e.message
  } finally {
    evaluating.value = false
  }
}

function costBadgeClass(cost: string) {
  if (cost === 'free') return 'bg-green-500/20 text-green-400'
  if (cost === 'ultra-cheap') return 'bg-blue-500/20 text-blue-400'
  return 'bg-yellow-500/20 text-yellow-400'
}

function returnClass(pct: number) {
  if (pct > 0) return 'text-green-400'
  if (pct < 0) return 'text-red-400'
  return 'text-gray-400'
}

onMounted(load)
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-white">AI Trader Arena</h1>
        <p class="text-sm text-gray-400 mt-1">9 autonomous AI traders competing with $10,000 each</p>
      </div>
      <button
        @click="runEvaluation"
        :disabled="evaluating"
        class="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500
               text-white text-sm font-medium rounded-lg transition-colors"
      >
        {{ evaluating ? 'Evaluating...' : 'Run Evaluation Round' }}
      </button>
    </div>

    <!-- Eval result banner -->
    <div v-if="evalResult" class="mb-4 p-3 bg-gray-800 rounded-lg border border-gray-700 text-sm">
      <span class="text-green-400 font-medium">Round complete:</span>
      <span class="text-gray-300 ml-2">
        {{ evalResult.llm_calls }} LLM calls |
        {{ evalResult.pre_filtered }} pre-filtered |
        {{ evalResult.trades_executed }} trades executed |
        {{ evalResult.hard_exits }} hard exits
      </span>
    </div>

    <LoadingSpinner v-if="loading" />
    <ErrorBox v-else-if="error" :message="error" />

    <template v-else>
      <!-- Stats cards -->
      <div class="grid grid-cols-4 gap-4 mb-6">
        <div class="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div class="text-xs text-gray-500 uppercase tracking-wide">Active Traders</div>
          <div class="text-2xl font-bold text-white mt-1">{{ leaderboard.length }}</div>
        </div>
        <div class="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div class="text-xs text-gray-500 uppercase tracking-wide">Total Portfolio Value</div>
          <div class="text-2xl font-bold text-white mt-1">${{ totalValue.toLocaleString('en', { minimumFractionDigits: 0 }) }}</div>
        </div>
        <div class="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div class="text-xs text-gray-500 uppercase tracking-wide">Total Trades</div>
          <div class="text-2xl font-bold text-white mt-1">{{ totalTrades }}</div>
        </div>
        <div class="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div class="text-xs text-gray-500 uppercase tracking-wide">Best Performer</div>
          <div class="text-lg font-bold mt-1" :class="bestTrader ? returnClass(bestTrader.total_return_pct) : 'text-gray-400'">
            {{ bestTrader ? `${bestTrader.name} (${bestTrader.total_return_pct >= 0 ? '+' : ''}${bestTrader.total_return_pct.toFixed(2)}%)` : '—' }}
          </div>
        </div>
      </div>

      <!-- Leaderboard table -->
      <div class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <div class="px-4 py-3 border-b border-gray-700">
          <h2 class="text-lg font-semibold text-white">Leaderboard</h2>
        </div>
        <table class="w-full text-sm">
          <thead class="bg-gray-900/50 text-gray-400 text-xs uppercase tracking-wide">
            <tr>
              <th class="px-4 py-3 text-left">#</th>
              <th class="px-4 py-3 text-left">Trader</th>
              <th class="px-4 py-3 text-left">Model</th>
              <th class="px-4 py-3 text-left">Cost</th>
              <th class="px-4 py-3 text-right">Portfolio Value</th>
              <th class="px-4 py-3 text-right">Return</th>
              <th class="px-4 py-3 text-right">Trades</th>
              <th class="px-4 py-3 text-right">Win Rate</th>
              <th class="px-4 py-3 text-right">Open Pos.</th>
              <th class="px-4 py-3 text-right">Cash</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="entry in leaderboard"
              :key="entry.trader_id"
              class="border-t border-gray-700/50 hover:bg-gray-700/30 cursor-pointer transition-colors"
              @click="$router.push(`/arena/${entry.slug}`)"
            >
              <td class="px-4 py-3 font-bold" :class="entry.rank <= 3 ? 'text-yellow-400' : 'text-gray-500'">
                {{ entry.rank }}
              </td>
              <td class="px-4 py-3">
                <div class="text-white font-medium">{{ entry.name }}</div>
                <div class="text-xs text-gray-500">{{ traders.find(t => t.slug === entry.slug)?.description?.style || '' }}</div>
              </td>
              <td class="px-4 py-3 text-gray-400 text-xs font-mono">
                {{ entry.llm_model.split('/').pop() }}
              </td>
              <td class="px-4 py-3">
                <span class="text-xs px-2 py-0.5 rounded-full"
                      :class="costBadgeClass(traders.find(t => t.slug === entry.slug)?.description?.cost || 'cheap')">
                  {{ traders.find(t => t.slug === entry.slug)?.description?.cost || 'cheap' }}
                </span>
              </td>
              <td class="px-4 py-3 text-right text-white font-mono">
                ${{ entry.portfolio_value_usd.toLocaleString('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}
              </td>
              <td class="px-4 py-3 text-right font-mono font-medium" :class="returnClass(entry.total_return_pct)">
                {{ entry.total_return_pct >= 0 ? '+' : '' }}{{ entry.total_return_pct.toFixed(2) }}%
              </td>
              <td class="px-4 py-3 text-right text-gray-300">
                {{ entry.total_trades }}
                <span class="text-xs text-gray-500 ml-1">
                  ({{ entry.wins }}W/{{ entry.losses }}L)
                </span>
              </td>
              <td class="px-4 py-3 text-right font-mono" :class="entry.win_rate_pct >= 50 ? 'text-green-400' : entry.win_rate_pct > 0 ? 'text-yellow-400' : 'text-gray-500'">
                {{ entry.total_trades > 0 ? entry.win_rate_pct.toFixed(0) + '%' : '—' }}
              </td>
              <td class="px-4 py-3 text-right text-gray-300">{{ entry.open_positions }}</td>
              <td class="px-4 py-3 text-right text-gray-400 font-mono text-xs">
                ${{ entry.cash_available.toLocaleString('en', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>
