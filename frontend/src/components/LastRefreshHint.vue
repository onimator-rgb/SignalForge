<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const now = ref(new Date())
let timer: ReturnType<typeof setInterval>

onMounted(() => { timer = setInterval(() => now.value = new Date(), 5000) })
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <span class="text-[10px] text-gray-600 tabular-nums">
    {{ now.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }}
  </span>
</template>
