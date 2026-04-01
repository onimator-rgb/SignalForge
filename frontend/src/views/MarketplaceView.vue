<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import api from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'

interface Strategy {
  id: number
  name: string
  description: string
  style: string
  is_public: boolean
  rules: Record<string, unknown>
  sharpe_ratio: number
  rank: number
}

type SortField = 'sharpe' | 'name'

const loading = ref(true)
const error = ref('')
const strategies = ref<Strategy[]>([])
const sortBy = ref<SortField>('sharpe')
const copyingId = ref<number | null>(null)
const copyFeedback = ref<Record<number, { ok: boolean; msg: string }>>({})

const styleColors: Record<string, string> = {
  aggressive: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  balanced: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  conservative: 'bg-green-500/20 text-green-400 border-green-500/30',
}

function styleClass(style: string): string {
  return styleColors[style] || 'bg-gray-500/20 text-gray-400 border-gray-500/30'
}

function sharpeColor(v: number): string {
  if (v > 1) return 'text-green-400'
  if (v >= 0) return 'text-yellow-400'
  return 'text-red-400'
}

const sorted = computed(() => {
  const list = [...strategies.value]
  if (sortBy.value === 'sharpe') {
    list.sort((a, b) => b.sharpe_ratio - a.sharpe_ratio)
  } else {
    list.sort((a, b) => a.name.localeCompare(b.name))
  }
  return list
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get('/strategies/marketplace/ranking')
    strategies.value = res.data
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

async function copyStrategy(id: number) {
  if (copyingId.value === id) return
  copyingId.value = id
  delete copyFeedback.value[id]
  try {
    await api.post(`/strategies/marketplace/${id}/copy`)
    copyFeedback.value[id] = { ok: true, msg: 'Skopiowano!' }
  } catch (e: any) {
    copyFeedback.value[id] = { ok: false, msg: e.response?.data?.detail || 'Błąd kopiowania' }
  } finally {
    setTimeout(() => {
      copyingId.value = null
    }, 1500)
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-5">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold text-white">Marketplace</h1>

      <div class="flex items-center gap-2 text-sm">
        <span class="text-gray-500">Sortuj:</span>
        <button
          class="px-3 py-1 rounded-lg transition-colors"
          :class="sortBy === 'sharpe'
            ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
            : 'text-gray-400 hover:text-gray-200 border border-gray-700 hover:border-gray-600'"
          @click="sortBy = 'sharpe'"
        >
          Sharpe ↓
        </button>
        <button
          class="px-3 py-1 rounded-lg transition-colors"
          :class="sortBy === 'name'
            ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
            : 'text-gray-400 hover:text-gray-200 border border-gray-700 hover:border-gray-600'"
          @click="sortBy = 'name'"
        >
          Nazwa A-Z
        </button>
      </div>
    </div>

    <LoadingSpinner v-if="loading" />
    <ErrorBox v-else-if="error" :message="error" />

    <div v-else-if="sorted.length === 0" class="text-gray-500 text-sm">
      Brak publicznych strategii w marketplace.
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      <div
        v-for="s in sorted"
        :key="s.id"
        class="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col gap-3"
      >
        <!-- Header: rank + name -->
        <div class="flex items-start gap-3">
          <span
            class="shrink-0 w-8 h-8 rounded-full bg-gray-800 border border-gray-700
                   flex items-center justify-center text-xs font-bold text-gray-300 tabular-nums"
          >
            #{{ s.rank }}
          </span>
          <div class="min-w-0 flex-1">
            <h3 class="text-white font-semibold text-sm truncate">{{ s.name }}</h3>
            <p class="text-gray-500 text-xs mt-0.5 line-clamp-2">{{ s.description }}</p>
          </div>
        </div>

        <!-- Metrics row -->
        <div class="flex items-center gap-3 text-sm">
          <span
            class="px-2 py-0.5 rounded-full text-xs font-medium border capitalize"
            :class="styleClass(s.style)"
          >
            {{ s.style }}
          </span>
          <span class="text-gray-500">Sharpe:</span>
          <span class="tabular-nums font-semibold" :class="sharpeColor(s.sharpe_ratio)">
            {{ s.sharpe_ratio.toFixed(2) }}
          </span>
        </div>

        <!-- Copy button + feedback -->
        <div class="mt-auto flex items-center gap-3">
          <button
            class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors
                   bg-blue-500/20 text-blue-400 border border-blue-500/30
                   hover:bg-blue-500/30 disabled:opacity-40 disabled:cursor-not-allowed"
            :disabled="copyingId === s.id"
            @click="copyStrategy(s.id)"
          >
            {{ copyingId === s.id ? 'Kopiowanie…' : 'Kopiuj strategię' }}
          </button>
          <span
            v-if="copyFeedback[s.id]"
            class="text-xs"
            :class="copyFeedback[s.id].ok ? 'text-green-400' : 'text-red-400'"
          >
            {{ copyFeedback[s.id].msg }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
