<script setup lang="ts">
defineProps<{ status: string }>()

const colors: Record<string, string> = {
  streaming: 'text-green-400 bg-green-500/10',
  live: 'text-green-400 bg-green-500/10',
  recent: 'text-blue-400 bg-blue-500/10',
  delayed: 'text-yellow-400 bg-yellow-500/10',
  stale: 'text-red-400 bg-red-500/10',
  error: 'text-red-400 bg-red-500/10',
  unavailable: 'text-gray-500 bg-gray-500/10',
}
</script>

<template>
  <span
    class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium"
    :class="colors[status] || colors.delayed"
  >
    <span
      class="w-1.5 h-1.5 rounded-full"
      :class="{
        'bg-green-400 animate-pulse': status === 'streaming' || status === 'live',
        'bg-blue-400': status === 'recent',
        'bg-yellow-400': status === 'delayed',
        'bg-red-400': status === 'stale' || status === 'error',
        'bg-gray-500': status === 'unavailable',
      }"
    />
    {{ status === 'streaming' ? 'live' : status }}
  </span>
</template>
