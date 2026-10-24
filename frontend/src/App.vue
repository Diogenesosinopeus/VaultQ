<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { Component } from 'vue'
import {
  Archive, BarChart3, BookOpenCheck, Check, ChevronRight, CircleHelp, Database,
  FileQuestion, Library, Menu, RefreshCw, Search, Send, ShieldCheck, Sparkles, X
} from 'lucide-vue-next'
import { api } from './api'
import CitationCard from './components/CitationCard.vue'
import type { AskResponse, ReviewResponse, SearchResponse, StatsResponse } from './types'

type ViewId = 'search' | 'ask' | 'review' | 'insights'

interface NavigationItem {
  id: ViewId
  label: string
  icon: Component
}

const views: NavigationItem[] = [
  { id: 'search', label: '目录检索', icon: Search },
  { id: 'ask', label: '档案问答', icon: Sparkles },
  { id: 'review', label: '温习案卷', icon: BookOpenCheck },
  { id: 'insights', label: '馆藏总览', icon: BarChart3 },
]
const activeView = ref<ViewId>('search')
const mobileNav = ref(false)
const query = ref('VaultQ 如何保证回答可追溯')
const askText = ref('VaultQ 找不到依据时会怎么做？')
const reviewTopic = ref('VaultQ')
const directory = ref('')
const selectedTag = ref('')
const searchResult = ref<SearchResponse | null>(null)
const askResult = ref<AskResponse | null>(null)
const reviewResult = ref<ReviewResponse | null>(null)
const stats = ref<StatsResponse | null>(null)
const busy = ref(false)
const error = ref('')
const indexing = ref(false)

const pageTitle = computed(() => views.find(item => item.id === activeView.value)?.label)
const hasData = computed(() => (stats.value?.documents || 0) > 0)

function selectView(id: ViewId): void {
  activeView.value = id
  mobileNav.value = false
}

async function loadStats(): Promise<void> {
  try { stats.value = await api.stats() } catch (err) { error.value = friendlyError(err) }
}

function friendlyError(_error: unknown): string {
  return '无法连接本地服务。请确认 VaultQ 后端已启动，然后重试。'
}

async function runSearch(): Promise<void> {
  if (!query.value.trim()) return
  busy.value = true; error.value = ''
  try { searchResult.value = await api.search(query.value.trim(), directory.value, selectedTag.value) }
  catch (err) { error.value = friendlyError(err) }
  finally { busy.value = false }
}

async function runAsk(): Promise<void> {
  if (!askText.value.trim()) return
  busy.value = true; error.value = ''
  try { askResult.value = await api.ask(askText.value.trim()) }
  catch (err) { error.value = friendlyError(err) }
  finally { busy.value = false }
}

async function runReview(): Promise<void> {
  busy.value = true; error.value = ''
  try { reviewResult.value = await api.review(reviewTopic.value.trim()) }
  catch (err) { error.value = friendlyError(err) }
  finally { busy.value = false }
}

async function rebuild(): Promise<void> {
  indexing.value = true; error.value = ''
  try {
    await api.index(); await loadStats()
    if (activeView.value === 'search' && query.value) await runSearch()
  } catch (err) { error.value = friendlyError(err) }
  finally { indexing.value = false }
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '尚未索引'
  return new Intl.DateTimeFormat('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

onMounted(async () => { await loadStats(); if (hasData.value) await runSearch() })
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar" :class="{ open: mobileNav }">
      <div class="brand">
        <div class="brand-mark"><Archive :size="23" /></div>
        <div><strong>VaultQ</strong><span>PRIVATE ARCHIVE</span></div>
        <button class="mobile-close" @click="mobileNav = false"><X :size="20" /></button>
      </div>

      <nav aria-label="主导航">
        <button v-for="item in views" :key="item.id" :class="{ active: activeView === item.id }" @click="selectView(item.id)">
          <component :is="item.icon" :size="19" />
          <span>{{ item.label }}</span>
          <ChevronRight v-if="activeView === item.id" :size="16" class="nav-arrow" />
        </button>
      </nav>

      <div class="scope-panel">
        <div class="scope-title"><Library :size="16" /> 馆藏分区</div>
        <div v-for="name in ['笔记', 'wiki', 'outputs']" :key="name" class="scope-row">
          <span>{{ name }}/</span><Check :size="14" />
        </div>
      </div>

      <div class="sidebar-footer">
        <div class="privacy"><ShieldCheck :size="17" /><div><strong>阅览模式</strong><span>原始档案保持只读</span></div></div>
        <button class="reindex" :disabled="indexing" @click="rebuild">
          <RefreshCw :size="16" :class="{ spin: indexing }" />{{ indexing ? '正在编目' : '重新编目' }}
        </button>
      </div>
    </aside>

    <main>
      <header class="topbar">
        <button class="menu-button" @click="mobileNav = true"><Menu :size="21" /></button>
        <div><span class="eyebrow">PRIVATE ARCHIVE · {{ pageTitle }}</span><h1>{{ pageTitle }}</h1></div>
        <div class="index-status"><span class="pulse" :class="{ offline: stats && !stats.ai.connected }"></span><div><strong>{{ stats?.documents ?? '—' }} 卷档案可调阅</strong><small>{{ stats?.ai.message || formatDate(stats?.last_indexed_at) }}</small></div></div>
      </header>

      <div v-if="error" class="error-banner"><CircleHelp :size="18" />{{ error }}<button @click="error = ''"><X :size="17" /></button></div>

      <section v-if="activeView === 'search'" class="page search-page">
        <div class="intro-line"><p>从馆藏中调阅确切原文。</p><span>CATALOGUE · {{ stats?.chunks ?? 0 }} 则条目</span></div>
        <form class="search-box" @submit.prevent="runSearch">
          <Search :size="23" />
          <input v-model="query" aria-label="搜索知识库" placeholder="输入题名、主题或一段疑问…" />
          <button :disabled="busy" type="submit">{{ busy ? '调阅中…' : '调阅' }}</button>
        </form>
        <div class="filters">
          <div class="filter-group"><span>目录</span><button v-for="item in ['', '笔记', 'wiki', 'outputs']" :key="item" :class="{ selected: directory === item }" @click="directory = item; query && runSearch()">{{ item || '全部' }}</button></div>
          <div v-if="stats?.tags?.length" class="filter-group tag-filter"><span>标签</span><button :class="{ selected: !selectedTag }" @click="selectedTag = ''; query && runSearch()">全部</button><button v-for="item in stats.tags.slice(0, 5)" :key="item.name" :class="{ selected: selectedTag === item.name }" @click="selectedTag = item.name; query && runSearch()">#{{ item.name }}</button></div>
        </div>

        <div v-if="searchResult" class="result-heading"><h2>{{ searchResult.total ? `调得 ${searchResult.total} 条档案` : '馆藏中没有依据' }}</h2><span v-if="searchResult.total">依相关程度排列</span></div>
        <div v-if="searchResult?.items?.length" class="citation-list"><CitationCard v-for="(item, index) in searchResult.items" :key="item.chunk_id" :citation="item" :index="index" /></div>
        <div v-else-if="searchResult" class="empty-state"><FileQuestion :size="34" /><h2>目录中没有相符条目</h2><p>可缩短问题、改用档案中的词语，或先补入相关资料。</p></div>
        <div v-else class="empty-state quiet"><Database :size="32" /><h2>请先填写调阅主题</h2><p>每项结果都会保留原始卷名、章节与行号。</p></div>
      </section>

      <section v-else-if="activeView === 'ask'" class="page two-column">
        <div class="primary-column">
          <div class="section-intro"><span class="section-number">I</span><div><h2>向馆藏提问</h2><p>仅依已调得的原文作答；不可考证之处将如实留白。</p></div><span class="model-badge" :class="{ offline: !stats?.ai.connected }">{{ stats?.ai.chat_ready ? '馆员助手在线' : '人工摘录模式' }}</span></div>
          <form class="ask-composer" @submit.prevent="runAsk"><textarea v-model="askText" rows="4" placeholder="请写下你要查证的问题…"></textarea><div><span><ShieldCheck :size="15" /> 引证校勘开启</span><button :disabled="busy"><Send :size="17" />{{ busy ? '查阅卷宗中' : '呈交问题' }}</button></div></form>
          <div v-if="askResult" class="answer-panel" :class="{ refusal: !askResult.grounded }">
            <div class="answer-head"><div><span class="answer-label">{{ askResult.mode === 'lm_studio' ? 'ARCHIVIST · 本地馆员' : 'VAULTQ · 原文摘录' }}</span><h2>{{ askResult.grounded ? '据馆藏资料答复' : '此问暂无可考' }}</h2></div><span class="confidence">可信度 · {{ askResult.confidence }}</span></div>
            <p class="answer-text">{{ askResult.answer }}</p>
          </div>
        </div>
        <aside class="evidence-column"><div class="evidence-title"><span>引证目录</span><strong>{{ askResult?.citations?.length ?? 0 }}</strong></div><div v-if="askResult?.citations?.length" class="citation-list compact"><CitationCard v-for="(item,index) in askResult.citations" :key="item.chunk_id" :citation="item" :index="index" /></div><div v-else class="evidence-empty"><Archive :size="29" /><p>呈交问题后，相关原文将列于此处。</p></div></aside>
      </section>

      <section v-else-if="activeView === 'review'" class="page review-page">
        <div class="review-hero"><div><span class="eyebrow">READ · RECALL · VERIFY</span><h2>把档案变成可温习的知识</h2><p>指定一项主题，馆员将依原文编排问题、提示与阅读次序。</p></div><form @submit.prevent="runReview"><input v-model="reviewTopic" placeholder="填写温习主题" /><button :disabled="busy">编制温习卷</button></form></div>
        <template v-if="reviewResult">
          <div class="review-grid">
            <div class="questions-panel"><div class="panel-heading"><span>温习题签</span><strong>{{ reviewResult.questions.length }}</strong></div><article v-for="(item,index) in reviewResult.questions" :key="item.citation.chunk_id" class="question-card"><span class="question-no">第 {{ index + 1 }} 题</span><h3>{{ item.question }}</h3><details><summary>启封答案线索</summary><p>{{ item.answer_hint }}</p><a :href="item.citation.obsidian_url">{{ item.citation.note_name }} · 第 {{ item.citation.line_start }} 行</a></details></article></div>
            <div class="review-side"><div class="path-panel"><div class="panel-heading"><span>建议路径</span></div><ol><li v-for="(step,index) in reviewResult.learning_path" :key="step"><span>{{ index + 1 }}</span>{{ step }}</li></ol></div><div class="gap-panel"><div class="panel-heading"><span>待补知识</span></div><p v-if="!reviewResult.gaps.length">当前检索范围内未发现明显缺口。</p><p v-for="gap in reviewResult.gaps" :key="gap">{{ gap }}</p></div></div>
          </div>
        </template>
        <div v-else class="empty-state quiet"><BookOpenCheck :size="35" /><h2>请先择一项温习主题</h2><p>所有题签与答案线索都可回溯至原始档案。</p></div>
      </section>

      <section v-else class="page insights-page">
        <div class="stat-grid"><div class="stat-card"><span>馆藏卷数</span><strong>{{ stats?.documents ?? 0 }}</strong><small>册 · Markdown 档案</small></div><div class="stat-card"><span>已编目条目</span><strong>{{ stats?.ai.embedded_chunks ?? 0 }}</strong><small>则 · Nomic 语义索引</small></div><div class="stat-card accent"><span>本地馆员</span><strong>{{ stats?.ai.connected ? '在席' : '离席' }}</strong><small>{{ stats?.ai.chat_ready ? 'Nemotron + Nomic' : '仍可人工摘录' }}</small></div></div>
        <div class="insight-grid"><div class="chart-panel"><div class="panel-heading"><span>资料分布</span></div><div v-if="stats?.directories?.length" class="bars"><div v-for="item in stats.directories" :key="item.name" class="bar-row"><span>{{ item.name }}/</span><div><i :style="{ width: `${Math.max(10, item.count / Math.max(...stats.directories.map(d => d.count)) * 100)}%` }"></i></div><strong>{{ item.count }}</strong></div></div><div v-else class="mini-empty">还没有可统计的笔记</div></div><div class="tag-panel"><div class="panel-heading"><span>主题标签</span></div><div v-if="stats?.tags?.length" class="tag-cloud"><span v-for="item in stats.tags" :key="item.name" :style="{ '--weight': Math.min(1.35, 0.9 + item.count * .08) }">#{{ item.name }} <small>{{ item.count }}</small></span></div><div v-else class="mini-empty">笔记中尚未发现标签</div></div></div>
        <div class="principle-panel"><ShieldCheck :size="25" /><div><h3>你的笔记留在本地</h3><p>索引数据库保存在知识库的 <code>.vaultq/</code> 目录。当前 API 没有修改笔记的能力。</p></div></div>
      </section>
    </main>
  </div>
</template>
