<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const showSlowMessage = ref(false)
let timer: ReturnType<typeof setTimeout>

onMounted(() => {
  timer = setTimeout(() => { showSlowMessage.value = true }, 5000)
})
onUnmounted(() => clearTimeout(timer))
</script>

<template>
  <div class="flex flex-col items-center justify-center py-12 gap-3">
    <div class="w-8 h-8 border-2 border-gray-600 border-t-blue-400 rounded-full animate-spin" />
    <div v-if="showSlowMessage" class="text-xs text-gray-500 animate-pulse">
      Ladowanie trwa dluzej niz zwykle...
    </div>
  </div>
</template>
