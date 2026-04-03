<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  fetchLeaderboard,
  fetchTraders,
  fetchTraderDecisions,
  fetchTraderPerformance,
  type LeaderboardEntry,
  type Trader,
  type TraderDecision,
  type PerformanceSnapshot,
} from '../api/arena'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'

const route = useRoute()
const router = useRouter()
const slug = computed(() => route.params.slug as string)

const trader = ref<Trader | null>(null)
const stats = ref<LeaderboardEntry | null>(null)
const decisions = ref<TraderDecision[]>([])
const performance = ref<PerformanceSnapshot[]>([])
const loading = ref(true)
const error = ref('')
const tab = ref<'decisions' | 'performance'>('decisions')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [traders, lb, decs, perf] = await Promise.all([
      fetchTraders(),
      fetchLeaderboard(),
      fetchTraderDecisions(slug.value, 100),
      fetchTraderPerformance(slug.value, 30),
    ])
    trader.value = traders.find(t => t.slug === slug.value) || null
    stats.value = lb.find(e => e.slug === slug.value) || null
    decisions.value = decs
    performance.value = perf
  } catch (e: any) {
    error.value = e.message || 'Failed to load trader'
  } finally {
    loading.value = false
  }
}

function actionBadge(action: string) {
  const map: Record<string, string> = {
    buy: 'bg-green-500/20 text-green-400',
    sell: 'bg-red-500/20 text-red-400',
    hold: 'bg-yellow-500/20 text-yellow-400',
    skip: 'bg-gray-500/20 text-gray-400',
  }
  return map[action] || 'bg-gray-500/20 text-gray-400'
}

function returnClass(pct: number) {
  if (pct > 0) return 'text-green-400'
  if (pct < 0) return 'text-red-400'
  return 'text-gray-400'
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('pl-PL', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(load)
</script>

<template>
  <div>
    <button @click="router.push('/arena')" class="text-sm text-gray-400 hover:text-white mb-4 inline-flex items-center gap-1">
      &larr; Back to Arena
    </button>

    <LoadingSpinner v-if="loading" />
    <ErrorBox v-else-if="error" :message="error" />

    <template v-else-if="trader && stats">
      <!-- Header -->
      <div class="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-6">
        <div class="flex items-start justify-between">
          <div>
            <h1 class="text-2xl font-bold text-white">{{ trader.name }}</h1>
            <p class="text-sm text-gray-400 mt-1">{{ trader.description.strategy }}</p>
            <div class="flex gap-3 mt-3">
              <span class="text-xs px-2 py-1 rounded bg-gray-700 text-gray-300">{{ trader.description.style }}</span>
              <span class="text-xs px-2 py-1 rounded bg-gray-700 text-gray-300 font-mono">{{ trader.llm_provider }}/{{ trader.llm_model.split('/').pop() }}</span>
              <span class="text-xs px-2 py-1 rounded"
                    :class="trader.description.cost === 'free' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'">
                {{ trader.description.cost }}
              </span>
            </div>
          </div>
          <div class="text-right">
            <div class="text-3xl font-bold font-mono" :class="returnClass(stats.total_return_pct)">
              {{ stats.total_return_pct >= 0 ? '+' : '' }}{{ stats.total_return_pct.toFixed(2) }}%
            </div>
            <div class="text-sm text-gray-400">Total Return</div>
          </div>
        </div>
      </div>

      <!-- Stats grid -->
      <div class="grid grid-cols-6 gap-3 mb-6">
        <div class="bg-gray-800 rounded-lg p-3 border border-gray-700 text-center">
          <div class="text-xs text-gray-500">Rank</div>
          <div class="text-xl font-bold" :class="stats.rank <= 3 ? 'text-yellow-400' : 'text-white'">#{{ stats.rank }}</div>
        </div>
        <div class="bg-gray-800 rounded-lg p-3 border border-gray-700 text-center">
          <div class="text-xs text-gray-500">Portfolio</div>
          <div class="text-lg font-bold text-white font-mono">${{ stats.portfolio_value_usd.toLocaleString('en', { maximumFractionDigits: 0 }) }}</div>
        </div>
        <div class="bg-gray-800 rounded-lg p-3 border border-gray-700 text-center">
          <div class="text-xs text-gray-500">Trades</div>
          <div class="text-lg font-bold text-white">{{ stats.total_trades }}</div>
        </div>
        <div class="bg-gray-800 rounded-lg p-3 border border-gray-700 text-center">
          <div class="text-xs text-gray-500">Win Rate</div>
          <div class="text-lg font-bold" :class="stats.win_rate_pct >= 50 ? 'text-green-400' : stats.win_rate_pct > 0 ? 'text-yellow-400' : 'text-gray-500'">
            {{ stats.total_trades > 0 ? stats.win_rate_pct.toFixed(0) + '%' : '—' }}
          </div>
        </div>
        <div class="bg-gray-800 rounded-lg p-3 border border-gray-700 text-center">
          <div class="text-xs text-gray-500">W / L</div>
          <div class="text-lg font-bold text-white">
            <span class="text-green-400">{{ stats.wins }}</span> / <span class="text-red-400">{{ stats.losses }}</span>
          </div>
        </div>
        <div class="bg-gray-800 rounded-lg p-3 border border-gray-700 text-center">
          <div class="text-xs text-gray-500">Open Pos.</div>
          <div class="text-lg font-bold text-white">{{ stats.open_positions }}</div>
        </div>
      </div>

      <!-- Tabs -->
      <div class="flex gap-2 mb-4">
        <button @click="tab = 'decisions'"
                class="px-4 py-2 text-sm rounded-lg transition-colors"
                :class="tab === 'decisions' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'">
          Recent Decisions ({{ decisions.length }})
        </button>
        <button @click="tab = 'performance'"
                class="px-4 py-2 text-sm rounded-lg transition-colors"
                :class="tab === 'performance' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'">
          Performance History
        </button>
      </div>

      <!-- Decisions tab -->
      <div v-if="tab === 'decisions'" class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <table class="w-full text-sm" v-if="decisions.length">
          <thead class="bg-gray-900/50 text-gray-400 text-xs uppercase tracking-wide">
            <tr>
              <th class="px-4 py-3 text-left">Time</th>
              <th class="px-4 py-3 text-left">Action</th>
              <th class="px-4 py-3 text-left">Confidence</th>
              <th class="px-4 py-3 text-left">Executed</th>
              <th class="px-4 py-3 text-left">Model</th>
              <th class="px-4 py-3 text-right">Latency</th>
              <th class="px-4 py-3 text-left">Reasoning</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in decisions" :key="d.id" class="border-t border-gray-700/50">
              <td class="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">{{ formatDate(d.created_at) }}</td>
              <td class="px-4 py-3">
                <span class="text-xs px-2 py-0.5 rounded-full font-medium" :class="actionBadge(d.action)">
                  {{ d.action.toUpperCase() }}
                </span>
              </td>
              <td class="px-4 py-3 font-mono text-gray-300">{{ (d.confidence * 100).toFixed(0) }}%</td>
              <td class="px-4 py-3">
                <span v-if="d.executed" class="text-green-400 text-xs">YES</span>
                <span v-else class="text-gray-600 text-xs">no</span>
              </td>
              <td class="px-4 py-3 text-xs text-gray-500 font-mono">{{ d.llm_model_used?.split('/').pop() || '—' }}</td>
              <td class="px-4 py-3 text-right text-xs text-gray-500">{{ d.latency_ms ? d.latency_ms + 'ms' : '—' }}</td>
              <td class="px-4 py-3 text-gray-400 text-xs max-w-md truncate">{{ d.reasoning }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="p-8 text-center text-gray-500">No decisions yet. Run an evaluation round first.</div>
      </div>

      <!-- Performance tab -->
      <div v-if="tab === 'performance'" class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <table class="w-full text-sm" v-if="performance.length">
          <thead class="bg-gray-900/50 text-gray-400 text-xs uppercase tracking-wide">
            <tr>
              <th class="px-4 py-3 text-left">Date</th>
              <th class="px-4 py-3 text-right">Portfolio Value</th>
              <th class="px-4 py-3 text-right">Total Return</th>
              <th class="px-4 py-3 text-right">Daily Return</th>
              <th class="px-4 py-3 text-right">Win Rate</th>
              <th class="px-4 py-3 text-right">Trades</th>
              <th class="px-4 py-3 text-right">Open Pos.</th>
              <th class="px-4 py-3 text-right">Cash</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in performance" :key="s.date" class="border-t border-gray-700/50">
              <td class="px-4 py-3 text-gray-300">{{ s.date }}</td>
              <td class="px-4 py-3 text-right text-white font-mono">${{ s.portfolio_value_usd.toLocaleString('en', { maximumFractionDigits: 2 }) }}</td>
              <td class="px-4 py-3 text-right font-mono" :class="returnClass(s.total_return_pct)">
                {{ s.total_return_pct >= 0 ? '+' : '' }}{{ s.total_return_pct.toFixed(2) }}%
              </td>
              <td class="px-4 py-3 text-right font-mono" :class="s.daily_return_pct !== null ? returnClass(s.daily_return_pct) : 'text-gray-500'">
                {{ s.daily_return_pct !== null ? (s.daily_return_pct >= 0 ? '+' : '') + s.daily_return_pct.toFixed(2) + '%' : '—' }}
              </td>
              <td class="px-4 py-3 text-right text-gray-300">{{ s.win_rate !== null ? (s.win_rate * 100).toFixed(0) + '%' : '—' }}</td>
              <td class="px-4 py-3 text-right text-gray-300">{{ s.total_trades }}</td>
              <td class="px-4 py-3 text-right text-gray-300">{{ s.open_positions }}</td>
              <td class="px-4 py-3 text-right text-gray-400 font-mono text-xs">${{ s.cash_usd.toLocaleString('en', { maximumFractionDigits: 0 }) }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="p-8 text-center text-gray-500">No performance data yet. Snapshots are taken daily.</div>
      </div>
    </template>
  </div>
</template>
