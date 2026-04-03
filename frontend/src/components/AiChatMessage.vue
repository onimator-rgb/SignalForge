<script setup lang="ts">
import { ref } from 'vue'
import { renderMarkdown } from '../utils/markdown'
import { submitFeedback } from '../api/assistant'

const props = defineProps<{
  id: string
  role: 'user' | 'assistant'
  content: string
  agentType?: string | null
  model?: string | null
  createdAt?: string
  feedbackScore?: number | null
}>()

const feedback = ref<number | null>(props.feedbackScore ?? null)
const feedbackSending = ref(false)

async function sendFeedback(score: number) {
  if (feedbackSending.value) return
  feedbackSending.value = true
  try {
    await submitFeedback(props.id, score)
    feedback.value = score
  } catch {
    // silent
  } finally {
    feedbackSending.value = false
  }
}

const agentLabels: Record<string, string> = {
  market_analyst: 'Market Analyst',
  education_coach: 'Education Coach',
}
</script>

<template>
  <div
    class="flex gap-3 py-3"
    :class="role === 'user' ? 'justify-end' : 'justify-start'"
  >
    <!-- Avatar -->
    <div
      v-if="role === 'assistant'"
      class="w-8 h-8 rounded-full flex items-center justify-center text-sm shrink-0"
      :class="agentType === 'education_coach'
        ? 'bg-green-500/20 text-green-400'
        : 'bg-blue-500/20 text-blue-400'"
    >
      {{ agentType === 'education_coach' ? 'E' : 'M' }}
    </div>

    <!-- Message bubble -->
    <div
      class="max-w-[80%] rounded-xl px-4 py-3 text-sm leading-relaxed"
      :class="role === 'user'
        ? 'bg-blue-600 text-white rounded-br-sm'
        : 'bg-gray-800 text-gray-200 border border-gray-700 rounded-bl-sm'"
    >
      <!-- Agent badge -->
      <div
        v-if="role === 'assistant' && agentType"
        class="flex items-center gap-2 mb-2 pb-2 border-b border-gray-700"
      >
        <span class="text-xs font-medium text-gray-400">
          {{ agentLabels[agentType] || agentType }}
        </span>
        <span v-if="model" class="text-xs text-gray-600">{{ model }}</span>
      </div>

      <!-- Content -->
      <div
        v-if="role === 'assistant'"
        class="prose prose-invert prose-sm max-w-none
               [&_h2]:text-base [&_h2]:font-semibold [&_h2]:mt-3 [&_h2]:mb-1
               [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:mt-2 [&_h3]:mb-1
               [&_ul]:my-1 [&_li]:my-0.5
               [&_strong]:text-white
               [&_code]:bg-gray-900 [&_code]:px-1 [&_code]:rounded [&_code]:text-blue-300
               [&_hr]:border-gray-700 [&_hr]:my-3"
        v-html="renderMarkdown(content)"
      />
      <div v-else class="whitespace-pre-wrap">{{ content }}</div>

      <!-- Feedback -->
      <div
        v-if="role === 'assistant' && id"
        class="flex items-center gap-2 mt-2 pt-2 border-t border-gray-700/50"
      >
        <button
          class="text-xs px-1.5 py-0.5 rounded transition-colors"
          :class="feedback === 1
            ? 'bg-green-500/20 text-green-400'
            : 'text-gray-600 hover:text-gray-400'"
          @click="sendFeedback(1)"
          :disabled="feedbackSending"
        >
          +
        </button>
        <button
          class="text-xs px-1.5 py-0.5 rounded transition-colors"
          :class="feedback === -1
            ? 'bg-red-500/20 text-red-400'
            : 'text-gray-600 hover:text-gray-400'"
          @click="sendFeedback(-1)"
          :disabled="feedbackSending"
        >
          -
        </button>
      </div>
    </div>

    <!-- User avatar -->
    <div
      v-if="role === 'user'"
      class="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-sm text-gray-300 shrink-0"
    >
      U
    </div>
  </div>
</template>
