<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
import AiChatMessage from '../components/AiChatMessage.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import {
  fetchSessions,
  fetchSession,
  deleteSession,
  streamMessage,
  type SessionOut,
  type MessageOut,
  type StreamMeta,
} from '../api/assistant'

// State
const sessions = ref<SessionOut[]>([])
const activeSessionId = ref<string | null>(null)
const messages = ref<MessageOut[]>([])
const inputText = ref('')
const sending = ref(false)
const streamingContent = ref('')
const error = ref('')
const loadingSessions = ref(true)
const messagesContainer = ref<HTMLElement | null>(null)

// Load sessions on mount
onMounted(async () => {
  await loadSessions()
  loadingSessions.value = false
})

async function loadSessions() {
  try {
    sessions.value = await fetchSessions()
  } catch {
    /* silent */
  }
}

async function selectSession(id: string) {
  activeSessionId.value = id
  error.value = ''
  try {
    const detail = await fetchSession(id)
    messages.value = detail.messages
    scrollToBottom()
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  }
}

function startNewSession() {
  activeSessionId.value = null
  messages.value = []
  streamingContent.value = ''
  error.value = ''
  inputText.value = ''
}

async function removeSession(id: string) {
  try {
    await deleteSession(id)
    sessions.value = sessions.value.filter((s) => s.id !== id)
    if (activeSessionId.value === id) startNewSession()
  } catch {
    /* silent */
  }
}

async function send() {
  const text = inputText.value.trim()
  if (!text || sending.value) return

  sending.value = true
  error.value = ''
  streamingContent.value = ''

  // Add user message immediately
  const userMsg: MessageOut = {
    id: 'temp-user',
    role: 'user',
    content: text,
    agent_type: null,
    llm_model: null,
    created_at: new Date().toISOString(),
    feedback_score: null,
  }
  messages.value.push(userMsg)
  inputText.value = ''
  scrollToBottom()

  // Stream response
  streamMessage(
    text,
    activeSessionId.value,
    (chunk) => {
      streamingContent.value += chunk
      scrollToBottom()
    },
    (meta: StreamMeta) => {
      // Streaming done — add assistant message
      const assistantMsg: MessageOut = {
        id: meta.message_id,
        role: 'assistant',
        content: streamingContent.value,
        agent_type: meta.agent_type,
        llm_model: meta.model,
        created_at: new Date().toISOString(),
        feedback_score: null,
      }
      messages.value.push(assistantMsg)
      streamingContent.value = ''
      sending.value = false

      // Update session ID
      if (meta.session_id) {
        activeSessionId.value = meta.session_id
        loadSessions() // Refresh sidebar
      }
      scrollToBottom()
    },
    (err) => {
      error.value = err
      sending.value = false
      streamingContent.value = ''
    },
  )
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

function fmtDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('pl-PL', { day: '2-digit', month: '2-digit' })
    + ' ' + d.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="flex h-[calc(100vh-5.5rem)] gap-4">
    <!-- Sessions Sidebar -->
    <div class="w-64 bg-gray-900 border border-gray-800 rounded-xl flex flex-col shrink-0">
      <div class="p-3 border-b border-gray-800 flex items-center justify-between">
        <h3 class="text-sm font-semibold text-gray-300">Rozmowy</h3>
        <button
          class="text-xs bg-blue-600 hover:bg-blue-500 text-white px-2 py-1 rounded transition-colors"
          @click="startNewSession"
        >
          + Nowa
        </button>
      </div>

      <div class="flex-1 overflow-auto p-2 space-y-1">
        <div v-if="loadingSessions" class="flex justify-center py-4">
          <LoadingSpinner />
        </div>

        <div
          v-for="s in sessions"
          :key="s.id"
          class="group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer text-sm transition-colors"
          :class="activeSessionId === s.id
            ? 'bg-gray-800 text-white'
            : 'text-gray-400 hover:bg-gray-800/50 hover:text-gray-300'"
          @click="selectSession(s.id)"
        >
          <div class="flex-1 min-w-0">
            <div class="truncate">{{ s.title || 'Nowa rozmowa' }}</div>
            <div class="text-xs text-gray-600">{{ fmtDate(s.updated_at) }}</div>
          </div>
          <button
            class="text-gray-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity text-xs"
            @click.stop="removeSession(s.id)"
            title="Usun"
          >
            x
          </button>
        </div>

        <div
          v-if="!loadingSessions && sessions.length === 0"
          class="text-center text-gray-600 text-xs py-4"
        >
          Brak rozmow. Zacznij nowa!
        </div>
      </div>
    </div>

    <!-- Chat Area -->
    <div class="flex-1 flex flex-col bg-gray-900 border border-gray-800 rounded-xl">
      <!-- Header -->
      <div class="p-4 border-b border-gray-800">
        <h2 class="text-lg font-semibold text-white">AI Asystent</h2>
        <p class="text-xs text-gray-500">
          Zapytaj o analize rynku, wskazniki techniczne, lub nauke tradingu
        </p>
      </div>

      <!-- Messages -->
      <div
        ref="messagesContainer"
        class="flex-1 overflow-auto p-4 space-y-1"
      >
        <!-- Welcome screen -->
        <div
          v-if="messages.length === 0 && !streamingContent"
          class="flex flex-col items-center justify-center h-full text-center"
        >
          <div class="text-4xl mb-4">
            <span class="text-blue-400">Signal</span><span class="text-gray-300">Forge</span>
          </div>
          <p class="text-gray-500 text-sm mb-6 max-w-md">
            AI Asystent pomoze Ci analizowac rynki, zrozumiec wskazniki techniczne i uczyc sie tradingu.
          </p>
          <div class="grid grid-cols-2 gap-2 max-w-lg">
            <button
              v-for="q in [
                'Przeanalizuj BTC',
                'Co to jest RSI?',
                'Jak dziala MACD?',
                'Analiza ETH',
              ]"
              :key="q"
              class="text-left text-xs bg-gray-800 border border-gray-700 rounded-lg px-3 py-2
                     text-gray-400 hover:text-gray-200 hover:border-gray-600 transition-colors"
              @click="inputText = q; send()"
            >
              {{ q }}
            </button>
          </div>
        </div>

        <!-- Messages list -->
        <AiChatMessage
          v-for="msg in messages"
          :key="msg.id"
          :id="msg.id"
          :role="msg.role as 'user' | 'assistant'"
          :content="msg.content"
          :agent-type="msg.agent_type"
          :model="msg.llm_model"
          :created-at="msg.created_at"
          :feedback-score="msg.feedback_score"
        />

        <!-- Streaming indicator -->
        <div v-if="streamingContent" class="flex gap-3 py-3">
          <div class="w-8 h-8 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-sm shrink-0">
            A
          </div>
          <div class="max-w-[80%] rounded-xl px-4 py-3 text-sm leading-relaxed bg-gray-800 text-gray-200 border border-gray-700 rounded-bl-sm whitespace-pre-wrap">
            {{ streamingContent }}<span class="animate-pulse text-blue-400">|</span>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="sending && !streamingContent" class="flex gap-3 py-3">
          <div class="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center shrink-0">
            <LoadingSpinner />
          </div>
          <div class="text-sm text-gray-500 self-center">Analizuje...</div>
        </div>
      </div>

      <!-- Error -->
      <div v-if="error" class="px-4 pb-2">
        <div class="text-xs text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
          {{ error }}
        </div>
      </div>

      <!-- Input -->
      <div class="p-4 border-t border-gray-800">
        <div class="flex gap-2">
          <textarea
            v-model="inputText"
            class="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-200
                   placeholder-gray-500 resize-none focus:outline-none focus:border-blue-500
                   transition-colors"
            :rows="1"
            placeholder="Napisz wiadomosc... (Enter = wyslij, Shift+Enter = nowa linia)"
            @keydown="handleKeydown"
            :disabled="sending"
          />
          <button
            class="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500
                   text-white text-sm font-medium rounded-xl transition-colors shrink-0"
            :disabled="sending || !inputText.trim()"
            @click="send"
          >
            Wyslij
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
