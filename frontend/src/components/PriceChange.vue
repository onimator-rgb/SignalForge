<script setup lang="ts">
defineProps<{ value: number | null | undefined }>()
</script>

<template>
  <span v-if="value == null" class="text-gray-500">—</span>
  <span v-else :class="value >= 0 ? 'text-green-400' : 'text-red-400'" class="font-medium tabular-nums">
    {{ value >= 0 ? '+' : '' }}{{ value.toFixed(2) }}%
  </span>
</template>
