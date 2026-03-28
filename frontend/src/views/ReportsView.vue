<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { fetchReports, generateReport } from '../api/reports'
import type { AnalysisReport } from '../types/api'
import { fmtTime } from '../utils/format'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'

const router = useRouter()
const loading = ref(true)
const error = ref('')
const reports = ref<AnalysisReport[]>([])
const total = ref(0)
const generating = ref(false)
const genError = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetchReports({ limit: 30 })
    reports.value = res.items
    total.value = res.total
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

async function genMarketSummary() {
  generating.value = true
  genError.value = ''
  try {
    const report = await generateReport({ report_type: 'market_summary' })
    router.push(`/reports/${report.id}`)
  } catch (e: any) {
    genError.value = e.response?.data?.detail || e.message
  } finally {
    generating.value = false
  }
}

onMounted(load)

const statusColors: Record<string, string> = {
  completed: 'text-green-400 bg-green-500/10 border-green-500/30',
  generating: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  pending: 'text-gray-400 bg-gray-500/10 border-gray-500/30',
  failed: 'text-red-400 bg-red-500/10 border-red-500/30',
}

const typeLabels: Record<string, string> = {
  asset_brief: 'Asset Brief',
  anomaly_explanation: 'Anomaly Explanation',
  market_summary: 'Market Summary',
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-5">
      <h1 class="text-2xl font-bold">Raporty AI</h1>
      <button
        class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg disabled:opacity-50"
        :disabled="generating"
        @click="genMarketSummary"
      >
        {{ generating ? 'Generowanie...' : 'Generuj Market Summary' }}
      </button>
    </div>

    <ErrorBox v-if="genError" :message="genError" />

    <LoadingSpinner v-if="loading" />
    <ErrorBox v-else-if="error" :message="error" />

    <template v-else>
      <div v-if="reports.length === 0" class="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center">
        <div class="text-gray-600 text-2xl mb-2">📄</div>
        <div class="text-sm text-gray-500">Brak raportow. Wygeneruj pierwszy klikajac przycisk powyzej.</div>
      </div>

      <div v-else class="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-xs text-gray-500 uppercase tracking-wide border-b border-gray-800">
              <th class="px-4 py-3 text-left">Typ</th>
              <th class="px-4 py-3 text-left">Tytul</th>
              <th class="px-4 py-3 text-center">Status</th>
              <th class="px-4 py-3 text-right">Model</th>
              <th class="px-4 py-3 text-right">Tokens</th>
              <th class="px-4 py-3 text-right">Utworzono</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="r in reports"
              :key="r.id"
              class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors cursor-pointer"
              @click="$router.push(`/reports/${r.id}`)"
            >
              <td class="px-4 py-3 text-gray-400 text-xs">{{ typeLabels[r.report_type] || r.report_type }}</td>
              <td class="px-4 py-3 text-white font-medium">{{ r.title || '—' }}</td>
              <td class="px-4 py-3 text-center">
                <span
                  class="inline-flex px-2 py-0.5 rounded text-xs font-medium border"
                  :class="statusColors[r.status] || statusColors.pending"
                >
                  {{ r.status }}
                </span>
              </td>
              <td class="px-4 py-3 text-right text-xs text-gray-500">{{ r.llm_model || '—' }}</td>
              <td class="px-4 py-3 text-right text-xs text-gray-500 tabular-nums">
                {{ r.token_usage ? `${(r.token_usage.input_tokens || 0) + (r.token_usage.output_tokens || 0)}` : '—' }}
              </td>
              <td class="px-4 py-3 text-right text-xs text-gray-400">{{ fmtTime(r.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>
