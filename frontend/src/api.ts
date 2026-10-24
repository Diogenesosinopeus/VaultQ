import type {
  AskResponse,
  IndexResponse,
  ReviewResponse,
  SearchResponse,
  StatsResponse,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000/api'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  })
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `请求失败：${response.status}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  stats: (): Promise<StatsResponse> => request('/stats'),
  index: (): Promise<IndexResponse> => request('/index', { method: 'POST' }),
  search: (query: string, directory = '', tag = ''): Promise<SearchResponse> => {
    const params = new URLSearchParams({ q: query, limit: '20' })
    if (directory) params.set('directory', directory)
    if (tag) params.set('tag', tag)
    return request(`/search?${params}`)
  },
  ask: (question: string): Promise<AskResponse> => request('/ask', {
    method: 'POST',
    body: JSON.stringify({ question, top_k: 6 }),
  }),
  review: (topic: string): Promise<ReviewResponse> => request('/review', {
    method: 'POST',
    body: JSON.stringify({ topic, count: 6 }),
  }),
}
