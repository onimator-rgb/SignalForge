<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchPerformance, type PerformanceMetrics } from '../api/performance'
import { fetchPortfolio, fetchRiskMetrics } from '../api/portfolio'
import type { PortfolioSummary, RiskMetrics } from '../types/api'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'

const loading = ref(true)
const error = ref('')
const perf = ref<PerformanceMetrics | null>(null)
const portfolio = ref<PortfolioSummary | null>(null)
const risk = ref<RiskMetrics | null>(null)
const riskLoading = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [p, pf] = await Promise.all([fetchPerformance(), fetchPortfolio()])
    perf.value = p
    portfolio.value = pf
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
  try {
    riskLoading.value = true
    risk.value = await fetchRiskMetrics()
  } catch {
    // risk metrics failure should not break the page
  } finally {
    riskLoading.value = false
  }
}

onMounted(load)

function fmtPct(val: number | null): string {
  if (val === null) return '--'
  return (val >= 0 ? '+' : '') + val.toFixed(2) + '%'
}

function pctClass(val: number | null): string {
  if (val === null) return 'text-gray-500'
  return val >= 0 ? 'text-green-400' : 'text-red-400'
}

function sharpeColor(val: number | null): string {
  if (val === null) return 'text-gray-500'
  if (val >= 1.0) return 'text-green-400'
  if (val >= 0.5) return 'text-yellow-400'
  return 'text-red-400'
}

function profitFactorColor(val: number | null): string {
  if (val === null) return 'text-gray-500'
  if (val >= 1.5) return 'text-green-400'
  if (val >= 1.0) return 'text-yellow-400'
  return 'text-red-400'
}

function reasonColor(reason: string): string {
  if (reason === 'stop_loss') return 'bg-red-900/60 text-red-300'
  if (reason === 'take_profit') return 'bg-green-900/60 text-green-300'
  if (reason === 'max_hold') return 'bg-blue-900/60 text-blue-300'
  return 'bg-gray-800 text-gray-400'
}

const typeLabels: Record<string, string> = {
  candidate_buy: 'BUY',
  watch_only: 'WATCH',
  neutral: 'NEUTRAL',
  avoid: 'AVOID',
}
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold mb-2">Performance</h1>
    <div class="text-[10px] text-gray-600 mb-5">
      Recommendation engine accuracy + demo portfolio metrics. Forward returns measured at 24h and 72h after signal generation.
    </div>

    <LoadingSpinner v-if="loading" />
    <ErrorBox v-else-if="error" :message="error" />

    <template v-else-if="perf">
      <!-- Summary cards -->
      <div class="grid grid-cols-6 gap-3 mb-6">
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-500 uppercase">Total recs</div>
          <div class="text-lg font-bold mt-1">{{ perf.summary.total_recommendations }}</div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-500 uppercase">Active</div>
          <div class="text-lg font-bold mt-1">{{ perf.summary.active_recommendations }}</div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-500 uppercase">Eval 24h</div>
          <div class="text-lg font-bold mt-1">{{ perf.summary.evaluated_24h }}</div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-500 uppercase">Eval 72h</div>
          <div class="text-lg font-bold mt-1">{{ perf.summary.evaluated_72h }}</div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-500 uppercase">Avg ret 24h</div>
          <div class="text-lg font-bold mt-1 tabular-nums" :class="pctClass(perf.summary.avg_return_24h_pct)">
            {{ fmtPct(perf.summary.avg_return_24h_pct) }}
          </div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div class="text-xs text-gray-500 uppercase">Avg ret 72h</div>
          <div class="text-lg font-bold mt-1 tabular-nums" :class="pctClass(perf.summary.avg_return_72h_pct)">
            {{ fmtPct(perf.summary.avg_return_72h_pct) }}
          </div>
        </div>
      </div>

      <!-- By version (calibration tracking) -->
      <div v-if="perf.by_version && perf.by_version.length > 0" class="mb-6">
        <div class="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <div class="px-4 py-3 border-b border-gray-800">
            <h2 class="text-sm font-semibold">By Scoring Version</h2>
          </div>
          <div class="flex divide-x divide-gray-800">
            <div v-for="v in perf.by_version" :key="v.version" class="flex-1 p-3 text-center">
              <div class="text-xs text-gray-500 mb-1">{{ v.version }}</div>
              <div class="text-sm font-bold">{{ v.total }} recs</div>
              <div class="text-xs text-gray-400">{{ v.evaluated }} evaluated</div>
              <div class="text-xs tabular-nums mt-1" :class="pctClass(v.avg_return_24h_pct)">
                24h: {{ fmtPct(v.avg_return_24h_pct) }}
              </div>
              <div class="text-xs text-gray-500">
                acc: {{ v.accuracy_24h_pct != null ? v.accuracy_24h_pct.toFixed(0) + '%' : '--' }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-3 gap-5 mb-6">
        <!-- By recommendation type -->
        <div class="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <div class="px-4 py-3 border-b border-gray-800">
            <h2 class="text-sm font-semibold">By Type</h2>
          </div>
          <table class="w-full text-xs">
            <thead>
              <tr class="text-gray-500 border-b border-gray-800">
                <th class="px-3 py-2 text-left">Type</th>
                <th class="px-3 py-2 text-right">Total</th>
                <th class="px-3 py-2 text-right">Eval</th>
                <th class="px-3 py-2 text-right">Avg 24h</th>
                <th class="px-3 py-2 text-right">Acc 24h</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in perf.by_type" :key="t.type" class="border-b border-gray-800/30">
                <td class="px-3 py-1.5 text-white font-medium">{{ typeLabels[t.type] || t.type }}</td>
                <td class="px-3 py-1.5 text-right text-gray-400">{{ t.total }}</td>
                <td class="px-3 py-1.5 text-right text-gray-400">{{ t.evaluated }}</td>
                <td class="px-3 py-1.5 text-right tabular-nums" :class="pctClass(t.avg_return_24h_pct)">{{ fmtPct(t.avg_return_24h_pct) }}</td>
                <td class="px-3 py-1.5 text-right tabular-nums text-gray-300">{{ t.accuracy_24h_pct != null ? t.accuracy_24h_pct.toFixed(0) + '%' : '--' }}</td>
              </tr>
              <tr v-if="perf.by_type.length === 0">
                <td colspan="5" class="px-3 py-4 text-center text-gray-500">No data yet</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- By asset class -->
        <div class="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <div class="px-4 py-3 border-b border-gray-800">
            <h2 class="text-sm font-semibold">By Asset Class</h2>
          </div>
          <table class="w-full text-xs">
            <thead>
              <tr class="text-gray-500 border-b border-gray-800">
                <th class="px-3 py-2 text-left">Class</th>
                <th class="px-3 py-2 text-right">Total</th>
                <th class="px-3 py-2 text-right">Eval</th>
                <th class="px-3 py-2 text-right">Avg 24h</th>
                <th class="px-3 py-2 text-right">Acc 24h</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in perf.by_asset_class" :key="c.asset_class" class="border-b border-gray-800/30">
                <td class="px-3 py-1.5 text-white font-medium">{{ c.asset_class }}</td>
                <td class="px-3 py-1.5 text-right text-gray-400">{{ c.total }}</td>
                <td class="px-3 py-1.5 text-right text-gray-400">{{ c.evaluated }}</td>
                <td class="px-3 py-1.5 text-right tabular-nums" :class="pctClass(c.avg_return_24h_pct)">{{ fmtPct(c.avg_return_24h_pct) }}</td>
                <td class="px-3 py-1.5 text-right tabular-nums text-gray-300">{{ c.accuracy_24h_pct != null ? c.accuracy_24h_pct.toFixed(0) + '%' : '--' }}</td>
              </tr>
              <tr v-if="perf.by_asset_class.length === 0">
                <td colspan="5" class="px-3 py-4 text-center text-gray-500">No data yet</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- By score bucket -->
        <div class="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <div class="px-4 py-3 border-b border-gray-800">
            <h2 class="text-sm font-semibold">By Score Bucket</h2>
          </div>
          <table class="w-full text-xs">
            <thead>
              <tr class="text-gray-500 border-b border-gray-800">
                <th class="px-3 py-2 text-left">Score</th>
                <th class="px-3 py-2 text-right">Total</th>
                <th class="px-3 py-2 text-right">Eval</th>
                <th class="px-3 py-2 text-right">Avg 24h</th>
                <th class="px-3 py-2 text-right">Acc 24h</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="b in perf.by_score_bucket" :key="b.bucket" class="border-b border-gray-800/30">
                <td class="px-3 py-1.5 text-white font-medium">{{ b.bucket }}</td>
                <td class="px-3 py-1.5 text-right text-gray-400">{{ b.total }}</td>
                <td class="px-3 py-1.5 text-right text-gray-400">{{ b.evaluated }}</td>
                <td class="px-3 py-1.5 text-right tabular-nums" :class="pctClass(b.avg_return_24h_pct)">{{ fmtPct(b.avg_return_24h_pct) }}</td>
                <td class="px-3 py-1.5 text-right tabular-nums text-gray-300">{{ b.accuracy_24h_pct != null ? b.accuracy_24h_pct.toFixed(0) + '%' : '--' }}</td>
              </tr>
              <tr v-if="perf.by_score_bucket.length === 0">
                <td colspan="5" class="px-3 py-4 text-center text-gray-500">No data yet</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Risk Metrics section -->
      <div class="mb-6">
        <h2 class="text-lg font-bold mb-3">Risk Metrics</h2>
        <div v-if="riskLoading" class="text-gray-500 text-sm">Loading risk metrics…</div>
        <div v-else-if="!risk || risk.total_closed === 0" class="bg-gray-900 border border-gray-800 rounded-lg p-6 text-center text-gray-500 text-sm">
          No risk data yet
        </div>
        <template v-else>
          <!-- 4-card grid -->
          <div class="grid grid-cols-4 gap-3 mb-3">
            <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
              <div class="text-xs text-gray-500 uppercase">Sharpe</div>
              <div class="text-lg font-bold mt-1 tabular-nums" :class="sharpeColor(risk.sharpe_ratio)">
                {{ risk.sharpe_ratio !== null ? risk.sharpe_ratio.toFixed(2) : '--' }}
              </div>
            </div>
            <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
              <div class="text-xs text-gray-500 uppercase">Max Drawdown</div>
              <div class="text-lg font-bold mt-1 tabular-nums text-red-400">
                {{ risk.max_drawdown_pct !== null ? '-' + risk.max_drawdown_pct.toFixed(2) + '%' : '--' }}
              </div>
            </div>
            <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
              <div class="text-xs text-gray-500 uppercase">Profit Factor</div>
              <div class="text-lg font-bold mt-1 tabular-nums" :class="profitFactorColor(risk.profit_factor)">
                {{ risk.profit_factor !== null ? risk.profit_factor.toFixed(2) : '--' }}
              </div>
            </div>
            <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
              <div class="text-xs text-gray-500 uppercase">Win Rate</div>
              <div class="text-lg font-bold mt-1 tabular-nums" :class="risk.win_rate !== null && risk.win_rate >= 50 ? 'text-green-400' : 'text-red-400'">
                {{ risk.win_rate !== null ? risk.win_rate.toFixed(1) + '%' : '--' }}
              </div>
              <div class="text-xs text-gray-500 mt-0.5">{{ risk.wins }}W / {{ risk.losses }}L</div>
            </div>
          </div>

          <!-- 2-column detail row -->
          <div class="grid grid-cols-2 gap-3 mb-3">
            <div class="bg-gray-900 border border-gray-800 rounded-lg p-3 flex items-center gap-4">
              <div>
                <div class="text-xs text-gray-500 uppercase">Sortino</div>
                <div class="text-sm font-bold tabular-nums" :class="sharpeColor(risk.sortino_ratio)">
                  {{ risk.sortino_ratio !== null ? risk.sortino_ratio.toFixed(2) : '--' }}
                </div>
              </div>
              <div>
                <div class="text-xs text-gray-500 uppercase">Avg Hold</div>
                <div class="text-sm font-bold tabular-nums text-gray-300">{{ risk.avg_hold_hours.toFixed(1) }}h</div>
              </div>
            </div>
            <div class="bg-gray-900 border border-gray-800 rounded-lg p-3 flex items-center gap-4">
              <div>
                <div class="text-xs text-gray-500 uppercase">Avg Win</div>
                <div class="text-sm font-bold tabular-nums text-green-400">{{ risk.avg_win_pct !== null ? '+' + risk.avg_win_pct.toFixed(2) + '%' : '--' }}</div>
              </div>
              <div>
                <div class="text-xs text-gray-500 uppercase">Avg Loss</div>
                <div class="text-sm font-bold tabular-nums text-red-400">{{ risk.avg_loss_pct !== null ? risk.avg_loss_pct.toFixed(2) + '%' : '--' }}</div>
              </div>
              <div>
                <div class="text-xs text-gray-500 uppercase">Best</div>
                <div class="text-sm font-bold tabular-nums text-green-400">{{ risk.best_trade_pct !== null ? '+' + risk.best_trade_pct.toFixed(2) + '%' : '--' }}</div>
              </div>
              <div>
                <div class="text-xs text-gray-500 uppercase">Worst</div>
                <div class="text-sm font-bold tabular-nums text-red-400">{{ risk.worst_trade_pct !== null ? risk.worst_trade_pct.toFixed(2) + '%' : '--' }}</div>
              </div>
            </div>
          </div>

          <!-- Close reason breakdown -->
          <div v-if="Object.keys(risk.breakdown_by_reason).length > 0" class="flex flex-wrap gap-2">
            <span
              v-for="(count, reason) in risk.breakdown_by_reason"
              :key="reason"
              class="px-2 py-1 rounded text-xs font-medium tabular-nums"
              :class="reasonColor(String(reason))"
            >
              {{ reason }}: {{ count }}
            </span>
          </div>
        </template>
      </div>

      <!-- Portfolio section -->
      <template v-if="portfolio">
        <h2 class="text-lg font-bold mb-3">Demo Portfolio</h2>
        <div class="grid grid-cols-6 gap-3">
          <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
            <div class="text-xs text-gray-500 uppercase">Equity</div>
            <div class="text-lg font-bold mt-1 tabular-nums">${{ portfolio.stats.equity.toFixed(2) }}</div>
          </div>
          <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
            <div class="text-xs text-gray-500 uppercase">Return</div>
            <div class="text-lg font-bold mt-1 tabular-nums" :class="pctClass(portfolio.stats.total_return_pct)">
              {{ fmtPct(portfolio.stats.total_return_pct) }}
            </div>
          </div>
          <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
            <div class="text-xs text-gray-500 uppercase">Realized PnL</div>
            <div class="text-lg font-bold mt-1 tabular-nums" :class="pctClass(portfolio.stats.total_realized_pnl)">
              ${{ portfolio.stats.total_realized_pnl.toFixed(2) }}
            </div>
          </div>
          <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
            <div class="text-xs text-gray-500 uppercase">Win Rate</div>
            <div class="text-lg font-bold mt-1">{{ portfolio.stats.win_rate != null ? portfolio.stats.win_rate.toFixed(0) + '%' : '--' }}</div>
          </div>
          <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
            <div class="text-xs text-gray-500 uppercase">Best Trade</div>
            <div class="text-lg font-bold mt-1 tabular-nums" :class="pctClass(portfolio.stats.best_trade_pct)">
              {{ fmtPct(portfolio.stats.best_trade_pct) }}
            </div>
          </div>
          <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
            <div class="text-xs text-gray-500 uppercase">Worst Trade</div>
            <div class="text-lg font-bold mt-1 tabular-nums" :class="pctClass(portfolio.stats.worst_trade_pct)">
              {{ fmtPct(portfolio.stats.worst_trade_pct) }}
            </div>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>
