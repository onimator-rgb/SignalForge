import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const requestId = err.response?.headers?.['x-request-id'] || '—'
    const status = err.response?.status || 'network'
    const detail = err.response?.data?.detail || err.message || 'Unknown error'
    const method = err.config?.method?.toUpperCase() || '?'
    const path = err.config?.url || '?'

    console.error(`[API] ${method} ${path} → ${status} [${requestId}] ${detail}`)

    return Promise.reject(err)
  },
)

export default api
