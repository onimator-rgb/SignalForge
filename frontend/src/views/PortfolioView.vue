<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { fetchPortfolio, triggerEvaluation } from '../api/portfolio'
import type { PortfolioSummary } from '../types/api'
import { fmtPrice, fmtTime } from '../utils/format'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'

const loading = ref(true)
const error = ref('')
const data = ref<PortfolioSummary | null>(null)
const evaluating = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await fetchPortfolio()
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

onMounted(load)

function pnlClass(val: number | null): string {
  if (val === null) return 'text-gray-500'
  return val >= 0 ? 'text-green-400' : 'text-red-400'
}

function pnlPrefix(val: number | null): string {
  if (val === null) return ''
  return val >= 0 ? '+' : ''
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
    </div>
    <div class="text-[10px] text-gray-600 mb-4 leading-tight">
      Paper trading only — not real money. Results are simulated based on delayed market data.
    </div>

    <LoadingSpinner v-if="loading" />
    <ErrorBox v-else-if="error" :message="error" />

    <template v-else-if="data">
      <!-- Stats row -->
      <div class="grid grid-cols-5 gap-3 mb-6">
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
          <div class="text-xs text-gray-500 uppercase">Positions</div>
          <div class="text-lg font-bold mt-1">{{ data.stats.open_positions }}/5</div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-500 uppercase">Win Rate</div>
          <div class="text-lg font-bold mt-1">{{ data.stats.win_rate != null ? data.stats.win_rate.toFixed(0) + '%' : '—' }}</div>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-6">
        <!-- Left: Open Positions -->
        <div>
          <h2 class="font-semibold text-sm mb-3">Otwarte pozycje ({{ data.open_positions.length }})</h2>
          <div v-if="data.open_positions.length === 0" class="bg-gray-900 border border-gray-800 rounded-lg p-6 text-center text-sm text-gray-500">
            Brak otwartych pozycji. System otworzy pozycje gdy pojawia sie silne sygnaly (score >= 65).
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="p in data.open_positions" :key="p.id"
              class="bg-gray-900 border border-gray-800 rounded-lg p-3"
            >
              <div class="flex items-center justify-between mb-1">
                <RouterLink :to="`/assets/${p.asset_id}`" class="font-medium text-white text-sm hover:text-blue-400">
                  {{ p.asset_symbol }}
                  <span class="text-[10px] text-gray-500 ml-1">{{ p.asset_class }}</span>
                </RouterLink>
                <span class="text-sm font-bold tabular-nums" :class="pnlClass(p.unrealized_pnl_pct)">
                  {{ pnlPrefix(p.unrealized_pnl_pct) }}{{ p.unrealized_pnl_pct?.toFixed(2) ?? '0.00' }}%
                </span>
              </div>
              <div class="flex justify-between text-xs text-gray-500">
                <span>Entry: ${{ fmtPrice(p.entry_price) }}</span>
                <span>Now: ${{ p.current_price ? fmtPrice(p.current_price) : '—' }}</span>
                <span :class="pnlClass(p.unrealized_pnl_usd)">{{ pnlPrefix(p.unrealized_pnl_usd) }}${{ p.unrealized_pnl_usd?.toFixed(2) ?? '0.00' }}</span>
              </div>
              <div class="flex justify-between text-[10px] text-gray-600 mt-1">
                <span>Qty: {{ p.quantity < 1 ? p.quantity.toFixed(6) : p.quantity.toFixed(2) }}</span>
                <span>Value: ${{ p.current_value_usd?.toFixed(2) ?? '—' }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Right: Closed + Transactions -->
        <div class="space-y-5">
          <div>
            <h2 class="font-semibold text-sm mb-3">Zamkniete pozycje</h2>
            <div v-if="data.recent_closed.length === 0" class="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center text-sm text-gray-500">
              Brak zamknietych pozycji.
            </div>
            <div v-else class="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
              <table class="w-full text-xs">
                <thead>
                  <tr class="text-gray-500 border-b border-gray-800">
                    <th class="px-3 py-2 text-left">Asset</th>
                    <th class="px-3 py-2 text-right">PnL</th>
                    <th class="px-3 py-2 text-right">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="p in data.recent_closed" :key="p.id" class="border-b border-gray-800/30">
                    <td class="px-3 py-1.5">
                      <RouterLink :to="`/assets/${p.asset_id}`" class="text-white hover:text-blue-400">{{ p.asset_symbol }}</RouterLink>
                    </td>
                    <td class="px-3 py-1.5 text-right tabular-nums" :class="pnlClass(p.realized_pnl_pct)">
                      {{ pnlPrefix(p.realized_pnl_pct) }}{{ p.realized_pnl_pct?.toFixed(2) ?? '—' }}%
                    </td>
                    <td class="px-3 py-1.5 text-right text-gray-500">{{ p.close_reason ?? '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

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
                    <td class="px-3 py-1.5 text-right text-gray-500">{{ fmtTime(tx.executed_at) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
