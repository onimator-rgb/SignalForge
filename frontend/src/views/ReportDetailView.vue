<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { fetchReport, retryReport } from '../api/reports'
import type { AnalysisReport } from '../types/api'
import { fmtTime } from '../utils/format'
import { renderMarkdown } from '../utils/markdown'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'

const route = useRoute()
const router = useRouter()
const reportId = computed(() => route.params.id as string)

const loading = ref(true)
const error = ref('')
const report = ref<AnalysisReport | null>(null)
const retrying = ref(false)

onMounted(async () => {
  try {
    report.value = await fetchReport(reportId.value)
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
})

async function doRetry() {
  if (!report.value) return
  retrying.value = true
  try {
    const newReport = await retryReport(report.value.id)
    router.push(`/reports/${newReport.id}`)
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    retrying.value = false
  }
}

const typeLabels: Record<string, string> = {
  asset_brief: 'Asset Brief',
  anomaly_explanation: 'Anomaly Explanation',
  market_summary: 'Market Summary',
}

const statusClasses: Record<string, string> = {
  completed: 'text-green-400 bg-green-500/10 border-green-500/30',
  generating: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  pending: 'text-gray-400 bg-gray-500/10 border-gray-500/30',
  failed: 'text-red-400 bg-red-500/10 border-red-500/30',
}

const totalTokens = computed(() => {
  if (!report.value?.token_usage) return null
  return (report.value.token_usage.input_tokens || 0) + (report.value.token_usage.output_tokens || 0)
})

const durationSec = computed(() => {
  const ms = (report.value?.token_usage as any)?.duration_ms
  if (!ms) return null
  return (ms / 1000).toFixed(1)
})

const hasContext = computed(() => {
  if (!report.value) return false
  return !!(report.value.asset_id || report.value.anomaly_event_id || report.value.alert_event_id)
})
</script>

<template>
  <div>
    <RouterLink to="/reports" class="text-sm text-gray-500 hover:text-gray-300 mb-4 inline-block">
      &larr; Raporty
    </RouterLink>

    <LoadingSpinner v-if="loading" />
    <ErrorBox v-else-if="error" :message="error" />

    <template v-else-if="report">
      <div class="mb-6">
        <div class="flex items-center gap-3 mb-2">
          <span class="text-xs px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/30">
            {{ typeLabels[report.report_type] || report.report_type }}
          </span>
          <span class="text-xs px-2 py-0.5 rounded border" :class="statusClasses[report.status] || statusClasses.pending">
            {{ report.status }}
          </span>
        </div>
        <h1 class="text-2xl font-bold">{{ report.title || 'Raport' }}</h1>
        <div class="text-xs text-gray-500 mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
          <span>{{ fmtTime(report.created_at) }}</span>
          <span v-if="report.llm_model">Model: {{ report.llm_model }}</span>
          <span v-if="totalTokens">Tokens: {{ totalTokens }}</span>
          <span v-if="durationSec">Czas: {{ durationSec }}s</span>
          <span v-if="report.prompt_version">Prompt: {{ report.prompt_version }}</span>
        </div>

        <!-- Context / origin bar -->
        <div v-if="hasContext" class="flex items-center gap-3 mt-3 text-xs">
          <span class="text-gray-600">Kontekst:</span>
          <RouterLink
            v-if="report.asset_id"
            :to="`/assets/${report.asset_id}`"
            class="inline-flex items-center gap-1 px-2 py-0.5 rounded
                   bg-gray-800 border border-gray-700 text-gray-300 hover:text-white hover:border-gray-600"
          >
            {{ report.asset_symbol || 'Aktywo' }} <span class="text-gray-600">&rarr;</span>
          </RouterLink>
          <RouterLink
            v-if="report.anomaly_event_id"
            to="/anomalies"
            class="inline-flex items-center gap-1 px-2 py-0.5 rounded
                   bg-gray-800 border border-gray-700 text-gray-300 hover:text-white hover:border-gray-600"
          >
            Anomalia <span class="text-gray-600">&rarr;</span>
          </RouterLink>
          <RouterLink
            v-if="report.alert_event_id"
            to="/alerts"
            class="inline-flex items-center gap-1 px-2 py-0.5 rounded
                   bg-orange-500/10 border border-orange-500/30 text-orange-400 hover:bg-orange-500/20"
          >
            Z alertu <span class="text-gray-600">&rarr;</span>
          </RouterLink>
        </div>
      </div>

      <!-- Failed -->
      <div v-if="report.status === 'failed'" class="bg-red-500/10 border border-red-500/30 rounded-lg p-5">
        <div class="text-red-400 font-medium mb-2">Generowanie nie powiodlo sie</div>
        <div class="text-red-400/70 text-xs mb-4">{{ report.error_message || 'Nieznany blad' }}</div>
        <button
          class="px-4 py-1.5 bg-red-600 hover:bg-red-500 text-white text-sm rounded-lg disabled:opacity-50"
          :disabled="retrying"
          @click="doRetry"
        >{{ retrying ? 'Ponawiam...' : 'Ponow generowanie' }}</button>
      </div>

      <!-- Content -->
      <div
        v-else-if="report.content_md"
        class="bg-gray-900 border border-gray-800 rounded-lg p-6 max-w-none
               [&_h1]:text-xl [&_h1]:font-bold [&_h1]:mt-6 [&_h1]:mb-3 [&_h1]:text-white
               [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:mt-5 [&_h2]:mb-2 [&_h2]:text-white
               [&_h3]:text-base [&_h3]:font-semibold [&_h3]:mt-4 [&_h3]:mb-2 [&_h3]:text-gray-200
               [&_p]:text-gray-300 [&_p]:mb-3 [&_p]:leading-relaxed [&_p]:text-sm
               [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-3 [&_ul]:text-gray-300 [&_ul]:text-sm
               [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-3 [&_ol]:text-gray-300 [&_ol]:text-sm
               [&_li]:mb-1.5
               [&_strong]:text-white [&_em]:text-gray-400
               [&_code]:bg-gray-800 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-xs [&_code]:text-blue-300
               [&_hr]:border-gray-700 [&_hr]:my-5"
        v-html="renderMarkdown(report.content_md)"
      />

      <!-- Generating -->
      <div v-else class="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center">
        <div class="w-8 h-8 border-2 border-gray-600 border-t-blue-400 rounded-full animate-spin mx-auto mb-3" />
        <div class="text-sm text-gray-500">Raport jest w trakcie generowania...</div>
      </div>
    </template>
  </div>
</template>
