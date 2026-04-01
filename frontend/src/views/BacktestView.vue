<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { runBacktest, type BacktestRequest, type BacktestResponse } from '../api/backtest'
import { fetchAssets } from '../api/assets'
import type { AssetListItem } from '../types/api'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'

const assets = ref<AssetListItem[]>([])
const selectedAssetId = ref('')
const lookbackDays = ref(30)
const profileName = ref('balanced')
const loading = ref(false)
const error = ref('')
const result = ref<BacktestResponse | null>(null)

onMounted(async () => {
  try {
    const res = await fetchAssets({ limit: 100 })
    assets.value = res.items
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    error.value = err.response?.data?.detail || err.message || 'Nie udało się załadować aktywów'
  }
})

async function submit() {
  if (!selectedAssetId.value) return
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const req: BacktestRequest = {
      asset_id: selectedAssetId.value,
      lookback_days: lookbackDays.value,
      profile_name: profileName.value,
    }
    result.value = await runBacktest(req)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    error.value = err.response?.data?.detail || err.message || 'Błąd podczas uruchamiania backtestu'
  } finally {
    loading.value = false
  }
}

function fmtPct(val: number): string {
  return (val >= 0 ? '+' : '') + val.toFixed(2) + '%'
}

function pnlClass(val: number): string {
  return val >= 0 ? 'text-green-400' : 'text-red-400'
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div>
      <h1 class="text-2xl font-bold text-white">Backtest</h1>
      <p class="text-sm text-gray-400 mt-1">
        Uruchom symulację strategii na danych historycznych i przeanalizuj wyniki.
      </p>
    </div>

    <!-- Form -->
    <div class="bg-gray-800 rounded-lg p-4 space-y-4">
      <div class="grid grid-cols-1 sm:grid-cols-4 gap-4 items-end">
        <!-- Asset select -->
        <div>
          <label class="block text-xs text-gray-400 mb-1">Aktywo</label>
          <select
            v-model="selectedAssetId"
            class="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200
                   focus:outline-none focus:border-blue-500"
          >
            <option value="" disabled>Wybierz aktywo…</option>
            <option v-for="a in assets" :key="a.id" :value="a.id">
              {{ a.symbol }} — {{ a.name }}
            </option>
          </select>
        </div>

        <!-- Lookback days -->
        <div>
          <label class="block text-xs text-gray-400 mb-1">Lookback (dni)</label>
          <input
            v-model.number="lookbackDays"
            type="number"
            min="1"
            max="365"
            class="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200
                   focus:outline-none focus:border-blue-500"
          />
        </div>

        <!-- Profile select -->
        <div>
          <label class="block text-xs text-gray-400 mb-1">Profil strategii</label>
          <select
            v-model="profileName"
            class="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200
                   focus:outline-none focus:border-blue-500"
          >
            <option value="balanced">Balanced</option>
            <option value="aggressive">Aggressive</option>
            <option value="conservative">Conservative</option>
          </select>
        </div>

        <!-- Run button -->
        <div>
          <button
            :disabled="loading || !selectedAssetId"
            class="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed
                   text-white text-sm font-medium rounded-lg px-4 py-2 transition-colors"
            @click="submit"
          >
            {{ loading ? 'Uruchamianie…' : 'Uruchom backtest' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <LoadingSpinner v-if="loading" />

    <!-- Error -->
    <ErrorBox v-if="error" :message="error" />

    <!-- Results -->
    <template v-if="result">
      <!-- Metrics grid -->
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div class="bg-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-400">Return</div>
          <div class="text-lg font-semibold tabular-nums" :class="pnlClass(result.total_return_pct)">
            {{ fmtPct(result.total_return_pct) }}
          </div>
        </div>
        <div class="bg-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-400">Max Drawdown</div>
          <div class="text-lg font-semibold tabular-nums text-red-400">
            {{ fmtPct(result.max_drawdown_pct) }}
          </div>
        </div>
        <div class="bg-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-400">Sharpe Ratio</div>
          <div class="text-lg font-semibold tabular-nums text-gray-200">
            {{ result.sharpe_ratio.toFixed(2) }}
          </div>
        </div>
        <div class="bg-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-400">Win Rate</div>
          <div class="text-lg font-semibold tabular-nums text-gray-200">
            {{ fmtPct(result.win_rate) }}
          </div>
        </div>
        <div class="bg-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-400">Profit Factor</div>
          <div class="text-lg font-semibold tabular-nums text-gray-200">
            {{ result.profit_factor.toFixed(2) }}
          </div>
        </div>
        <div class="bg-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-400">Total Trades</div>
          <div class="text-lg font-semibold tabular-nums text-gray-200">
            {{ result.total_trades }}
          </div>
        </div>
      </div>

      <!-- Trade table -->
      <div class="bg-gray-800 rounded-lg overflow-hidden">
        <div class="px-4 py-3 border-b border-gray-700">
          <h2 class="text-sm font-semibold text-gray-200">Lista transakcji</h2>
        </div>
        <div class="overflow-x-auto max-h-96 overflow-y-auto">
          <table class="w-full text-sm text-left">
            <thead class="text-xs text-gray-400 bg-gray-900/50 sticky top-0">
              <tr>
                <th class="px-4 py-2">#</th>
                <th class="px-4 py-2">Side</th>
                <th class="px-4 py-2 text-right">Entry Price</th>
                <th class="px-4 py-2 text-right">Exit Price</th>
                <th class="px-4 py-2 text-right">PnL%</th>
                <th class="px-4 py-2">Exit Reason</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(trade, idx) in result.trades"
                :key="idx"
                class="border-t border-gray-700/50"
                :class="idx % 2 === 0 ? 'bg-gray-800' : 'bg-gray-800/50'"
              >
                <td class="px-4 py-2 text-gray-400 tabular-nums">{{ idx + 1 }}</td>
                <td class="px-4 py-2 text-gray-300 uppercase">{{ trade.side }}</td>
                <td class="px-4 py-2 text-right text-gray-300 tabular-nums">{{ trade.entry_price.toFixed(2) }}</td>
                <td class="px-4 py-2 text-right text-gray-300 tabular-nums">{{ trade.exit_price.toFixed(2) }}</td>
                <td class="px-4 py-2 text-right tabular-nums" :class="pnlClass(trade.pnl_pct)">
                  {{ fmtPct(trade.pnl_pct) }}
                </td>
                <td class="px-4 py-2 text-gray-400">{{ trade.exit_reason }}</td>
              </tr>
            </tbody>
          </table>
          <div v-if="result.trades.length === 0" class="px-4 py-6 text-center text-gray-500 text-sm">
            Brak transakcji w wybranym okresie.
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
