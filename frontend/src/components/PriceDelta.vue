<script setup lang="ts">
import { computed } from 'vue'
import { fmtPrice } from '../utils/format'

const props = defineProps<{
  entryPrice: number | null
  currentPrice: number | null
}>()

const delta = computed(() => {
  if (!props.entryPrice || !props.currentPrice || props.entryPrice <= 0) return null
  return ((props.currentPrice - props.entryPrice) / props.entryPrice) * 100
})
</script>

<template>
  <span v-if="delta !== null" class="tabular-nums text-xs" :class="delta >= 0 ? 'text-green-400' : 'text-red-400'">
    {{ delta >= 0 ? '+' : '' }}{{ delta.toFixed(2) }}%
  </span>
</template>
