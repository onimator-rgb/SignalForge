<script setup lang="ts">
defineProps<{ message?: string }>()
</script>

<template>
  <div class="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 text-sm">
    {{ message || 'Wystapil blad podczas ladowania danych.' }}
  </div>
</template>
