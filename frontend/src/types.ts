export interface Citation {
  chunk_id: number
  note_name: string
  path: string
  heading: string
  line_start: number
  line_end: number
  excerpt: string
  tags: string[]
  score: number
  obsidian_url: string
}

export interface SearchResponse {
  query: string
  total: number
  items: Citation[]
}

export interface AskResponse {
  answer: string
  grounded: boolean
  confidence: string
  mode: 'lm_studio' | 'extractive' | 'refusal'
  citations: Citation[]
}

export interface ReviewQuestion {
  question: string
  answer_hint: string
  citation: Citation
}

export interface ReviewResponse {
  topic: string
  questions: ReviewQuestion[]
  learning_path: string[]
  gaps: string[]
}

export interface CountItem {
  name: string
  count: number
}

export interface StatsResponse {
  documents: number
  chunks: number
  tags: CountItem[]
  directories: CountItem[]
  last_indexed_at: string | null
  root: string
  read_only: boolean
  ai: AIStatus
}

export interface AIStatus {
  connected: boolean
  chat_ready: boolean
  embedding_ready: boolean
  chat_model: string
  embedding_model: string
  embedded_chunks: number
  message: string
}

export interface IndexResponse {
  indexed_files: number
  indexed_chunks: number
  skipped_files: number
  removed_files: number
  embedded_chunks: number
  embedding_model: string | null
}
