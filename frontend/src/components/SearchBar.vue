<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { searchAssets } from '../api/assets'
import type { AssetSearchResult } from '../types/api'

const router = useRouter()
const query = ref('')
const results = ref<AssetSearchResult[]>([])
const isOpen = ref(false)
let debounceTimer: ReturnType<typeof setTimeout>

watch(query, (val) => {
  clearTimeout(debounceTimer)
  if (val.trim().length < 1) {
    results.value = []
    isOpen.value = false
    return
  }
  debounceTimer = setTimeout(async () => {
    try {
      results.value = await searchAssets(val.trim())
      isOpen.value = results.value.length > 0
    } catch {
      results.value = []
    }
  }, 250)
})

function select(asset: AssetSearchResult) {
  query.value = ''
  results.value = []
  isOpen.value = false
  router.push(`/assets/${asset.id}`)
}

function onBlur() {
  setTimeout(() => { isOpen.value = false }, 150)
}
</script>

<template>
  <div class="relative w-full">
    <input
      v-model="query"
      type="text"
      placeholder="Szukaj aktywa..."
      class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm
             text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500"
      @focus="isOpen = results.length > 0"
      @blur="onBlur"
    />
    <div
      v-if="isOpen"
      class="absolute top-full left-0 right-0 mt-1 bg-gray-800 border border-gray-700
             rounded-lg shadow-xl z-50 max-h-64 overflow-auto"
    >
      <button
        v-for="r in results"
        :key="r.id"
        class="w-full flex items-center gap-3 px-3 py-2 text-sm hover:bg-gray-700 text-left"
        @mousedown.prevent="select(r)"
      >
        <img
          v-if="r.image_url"
          :src="r.image_url"
          class="w-5 h-5 rounded-full"
          :alt="r.symbol"
        />
        <span class="font-medium text-white">{{ r.symbol }}</span>
        <span class="text-gray-400">{{ r.name }}</span>
        <span v-if="r.market_cap_rank" class="ml-auto text-xs text-gray-500">#{{ r.market_cap_rank }}</span>
      </button>
    </div>
  </div>
</template>
