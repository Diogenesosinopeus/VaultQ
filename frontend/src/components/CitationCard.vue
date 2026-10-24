<script setup lang="ts">
import { computed, ref } from 'vue'
import { BookOpen, ChevronDown, ExternalLink, FileText } from 'lucide-vue-next'
import type { Citation } from '../types'

const props = withDefaults(defineProps<{
  citation: Citation
  index?: number
}>(), { index: 0 })
const expanded = ref(false)
const lines = computed(() => props.citation.line_start === props.citation.line_end
  ? `第 ${props.citation.line_start} 行`
  : `第 ${props.citation.line_start}–${props.citation.line_end} 行`)
</script>

<template>
  <article class="citation-card">
    <div class="citation-index">{{ String(index + 1).padStart(2, '0') }}</div>
    <div class="citation-body">
      <div class="citation-topline">
        <div>
          <h3>{{ citation.note_name }}</h3>
          <p class="breadcrumb">{{ citation.heading }}</p>
        </div>
        <a class="open-link" :href="citation.obsidian_url" aria-label="在 Obsidian 中打开">
          <ExternalLink :size="17" />
          <span>打开原文</span>
        </a>
      </div>
      <blockquote :class="{ expanded }">{{ citation.excerpt }}</blockquote>
      <div class="citation-meta">
        <span><FileText :size="14" /> {{ citation.path }}</span>
        <span><BookOpen :size="14" /> {{ lines }}</span>
        <button class="text-button" type="button" @click="expanded = !expanded">
          {{ expanded ? '收起' : '展开片段' }} <ChevronDown :size="14" :class="{ rotate: expanded }" />
        </button>
      </div>
      <div v-if="citation.tags?.length" class="tag-row">
        <span v-for="tag in citation.tags" :key="tag" class="tag">#{{ tag }}</span>
      </div>
    </div>
  </article>
</template>
