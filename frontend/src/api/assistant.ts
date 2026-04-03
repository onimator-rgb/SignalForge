import api from './client'

export interface ChatResponse {
  session_id: string
  message_id: string
  content: string
  agent_type: string
  model: string
  provider: string
  input_tokens: number
  output_tokens: number
  latency_ms: number
}

export interface SessionOut {
  id: string
  title: string | null
  agent_type: string
  message_count: number
  created_at: string
  updated_at: string
}

export interface MessageOut {
  id: string
  role: string
  content: string
  agent_type: string | null
  llm_model: string | null
  created_at: string
  feedback_score: number | null
}

export interface SessionDetailOut extends SessionOut {
  messages: MessageOut[]
}

export interface StreamMeta {
  type: string
  session_id: string
  message_id: string
  agent_type: string
  model: string
  provider: string
  input_tokens: number
  output_tokens: number
  latency_ms: number
}

export interface AgentInfo {
  name: string
  description: string
  complexity: string
}

export async function sendMessage(message: string, sessionId?: string): Promise<ChatResponse> {
  const { data } = await api.post('/ai/chat', { message, session_id: sessionId || null })
  return data
}

export function streamMessage(
  message: string,
  sessionId: string | null,
  onChunk: (text: string) => void,
  onDone: (meta: StreamMeta) => void,
  onError: (err: string) => void,
): AbortController {
  const controller = new AbortController()
  const baseUrl = (import.meta.env.VITE_API_BASE_URL || '') + '/api/v1'
  const params = new URLSearchParams({ message })
  if (sessionId) params.set('session_id', sessionId)

  const url = `${baseUrl}/ai/chat/stream?${params.toString()}`

  fetch(url, { signal: controller.signal })
    .then(async (res) => {
      if (!res.ok) {
        onError(`HTTP ${res.status}`)
        return
      }
      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('event: meta')) {
            // Next data line is meta JSON
            continue
          }
          if (line.startsWith('event: done')) {
            continue
          }
          if (line.startsWith('data: ')) {
            const payload = line.slice(6)
            // Check if it's meta JSON
            try {
              const parsed = JSON.parse(payload)
              if (parsed.type === 'done') {
                onDone(parsed as StreamMeta)
                continue
              }
            } catch {
              // Regular text chunk
            }
            if (payload.trim()) {
              onChunk(payload)
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onError(err.message)
      }
    })

  return controller
}

export async function fetchSessions(): Promise<SessionOut[]> {
  const { data } = await api.get('/ai/sessions')
  return data
}

export async function fetchSession(id: string): Promise<SessionDetailOut> {
  const { data } = await api.get(`/ai/sessions/${id}`)
  return data
}

export async function deleteSession(id: string): Promise<void> {
  await api.delete(`/ai/sessions/${id}`)
}

export async function submitFeedback(messageId: string, score: number): Promise<void> {
  await api.post('/ai/feedback', { message_id: messageId, score })
}

export async function fetchAgents(): Promise<AgentInfo[]> {
  const { data } = await api.get('/ai/agents')
  return data
}
