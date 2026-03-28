<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { fetchAssets } from '../api/assets'
import type { AssetListItem } from '../types/api'
import { fmtPrice } from '../utils/format'
import PriceChange from '../components/PriceChange.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'

const initialLoading = ref(true)
const refetching = ref(false)
const error = ref('')
const items = ref<AssetListItem[]>([])
const total = ref(0)
const sortBy = ref('market_cap_rank')
const sortDir = ref('asc')
const page = ref(0)
const pageSize = 25
const filterClass = ref('')

async function load(isRefetch = false) {
  if (isRefetch) {
    refetching.value = true
  } else {
    initialLoading.value = true
  }
  error.value = ''
  try {
    const params: Record<string, unknown> = {
      sort_by: sortBy.value,
      sort_dir: sortDir.value,
      limit: pageSize,
      offset: page.value * pageSize,
    }
    if (filterClass.value) params.asset_class = filterClass.value
    const res = await fetchAssets(params as any)
    items.value = res.items
    total.value = res.total
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    initialLoading.value = false
    refetching.value = false
  }
}

onMounted(() => load(false))

watch(filterClass, () => {
  page.value = 0
  load(true)
})

function setSort(field: string) {
  if (sortBy.value === field) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = field
    sortDir.value = field === 'market_cap_rank' || field === 'symbol' ? 'asc' : 'desc'
  }
  page.value = 0
  load(true)
}

function sortArrow(field: string): string {
  if (sortBy.value !== field) return ''
  return sortDir.value === 'asc' ? ' \u25B2' : ' \u25BC'
}

function goPage(p: number) {
  page.value = p
  load(true)
}

const classColors: Record<string, string> = {
  crypto: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  stock: 'text-green-400 bg-green-500/10 border-green-500/30',
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-5">
      <h1 class="text-2xl font-bold">Aktywa</h1>
      <div class="flex gap-1">
        <button
          v-for="opt in [{ value: '', label: 'Wszystkie' }, { value: 'crypto', label: 'Crypto' }, { value: 'stock', label: 'Stocks' }]"
          :key="opt.value"
          class="px-3 py-1 text-xs rounded-lg border transition-colors"
          :class="filterClass === opt.value
            ? 'bg-blue-600/20 border-blue-500/40 text-blue-400'
            : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-gray-200'"
          @click="filterClass = opt.value"
        >{{ opt.label }}</button>
      </div>
    </div>

    <LoadingSpinner v-if="initialLoading" />
    <ErrorBox v-else-if="error" :message="error" />

    <template v-else>
      <div
        class="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden relative"
        :class="{ 'opacity-60 pointer-events-none': refetching }"
      >
        <div v-if="refetching" class="absolute inset-0 flex items-center justify-center z-10">
          <div class="w-6 h-6 border-2 border-gray-600 border-t-blue-400 rounded-full animate-spin" />
        </div>

        <table class="w-full text-sm">
          <thead>
            <tr class="text-xs text-gray-500 uppercase tracking-wide border-b border-gray-800">
              <th class="px-4 py-3 text-left cursor-pointer hover:text-gray-300 select-none" @click="setSort('market_cap_rank')">
                #{{ sortArrow('market_cap_rank') }}
              </th>
              <th class="px-4 py-3 text-left cursor-pointer hover:text-gray-300 select-none" @click="setSort('symbol')">
                Aktywo{{ sortArrow('symbol') }}
              </th>
              <th class="px-4 py-3 text-center">Typ</th>
              <th class="px-4 py-3 text-right cursor-pointer hover:text-gray-300 select-none" @click="setSort('latest_price')">
                Cena{{ sortArrow('latest_price') }}
              </th>
              <th class="px-4 py-3 text-right cursor-pointer hover:text-gray-300 select-none" @click="setSort('change_24h')">
                24h{{ sortArrow('change_24h') }}
              </th>
              <th class="px-4 py-3 text-right">Anomalie</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="items.length === 0">
              <td colspan="6" class="px-4 py-8 text-center text-gray-500">Brak aktywow do wyswietlenia.</td>
            </tr>
            <tr
              v-for="a in items"
              :key="a.id"
              class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors"
            >
              <td class="px-4 py-3 text-gray-500 tabular-nums">{{ a.market_cap_rank ?? '—' }}</td>
              <td class="px-4 py-3">
                <RouterLink :to="`/assets/${a.id}`" class="flex items-center gap-2.5 hover:text-white">
                  <img v-if="a.image_url" :src="a.image_url" class="w-6 h-6 rounded-full" :alt="a.symbol" />
                  <div>
                    <div class="font-medium text-white">{{ a.symbol }}</div>
                    <div class="text-xs text-gray-500">{{ a.name }}</div>
                  </div>
                </RouterLink>
              </td>
              <td class="px-4 py-3 text-center">
                <span
                  class="inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium border"
                  :class="classColors[a.asset_class] || classColors.crypto"
                >{{ a.asset_class }}</span>
              </td>
              <td class="px-4 py-3 text-right tabular-nums text-gray-300">
                {{ a.latest_price ? '$' + fmtPrice(a.latest_price.close) : '—' }}
              </td>
              <td class="px-4 py-3 text-right">
                <PriceChange :value="a.latest_price?.change_24h_pct" />
              </td>
              <td class="px-4 py-3 text-right">
                <span
                  v-if="a.unresolved_anomalies > 0"
                  class="inline-flex items-center justify-center min-w-5 h-5 rounded-full bg-orange-500/20 text-orange-400 text-xs font-medium px-1.5"
                >
                  {{ a.unresolved_anomalies }}
                </span>
                <span v-else class="text-gray-600">0</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div v-if="total > pageSize" class="flex items-center justify-between mt-4 text-sm text-gray-500">
        <span>{{ page * pageSize + 1 }}–{{ Math.min((page + 1) * pageSize, total) }} z {{ total }}</span>
        <div class="flex gap-2">
          <button
            :disabled="page === 0"
            class="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed"
            @click="goPage(page - 1)"
          >Wstecz</button>
          <button
            :disabled="(page + 1) * pageSize >= total"
            class="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed"
            @click="goPage(page + 1)"
          >Dalej</button>
        </div>
      </div>
    </template>
  </div>
</template>
