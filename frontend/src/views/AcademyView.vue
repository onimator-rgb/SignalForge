<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'

interface ArticleListItem {
  slug: string
  title: string
  category: string
  summary: string
}

interface ArticleDetail extends ArticleListItem {
  body: string
}

const articles = ref<ArticleListItem[]>([])
const selectedArticle = ref<ArticleDetail | null>(null)
const activeCategory = ref('all')
const loading = ref(false)
const error = ref('')
const detailLoading = ref(false)
const detailError = ref('')

const categories = [
  { key: 'all', label: 'Wszystkie' },
  { key: 'indicators', label: 'Wskazniki' },
  { key: 'strategies', label: 'Strategie' },
  { key: 'risk', label: 'Ryzyko' },
]

const categoryColors: Record<string, string> = {
  indicators: 'bg-blue-500/20 text-blue-400',
  strategies: 'bg-purple-500/20 text-purple-400',
  risk: 'bg-yellow-500/20 text-yellow-400',
}

function getCategoryBadgeClass(category: string): string {
  return categoryColors[category] ?? 'bg-gray-500/20 text-gray-400'
}

async function fetchArticles(category: string) {
  loading.value = true
  error.value = ''
  try {
    const params = category !== 'all' ? { category } : {}
    const res = await api.get<ArticleListItem[]>('/academy/articles', { params })
    articles.value = res.data
  } catch {
    error.value = 'Nie udalo sie zaladowac artykulow.'
  } finally {
    loading.value = false
  }
}

async function selectArticle(slug: string) {
  detailLoading.value = true
  detailError.value = ''
  try {
    const res = await api.get<ArticleDetail>(`/academy/articles/${slug}`)
    selectedArticle.value = res.data
  } catch {
    detailError.value = 'Nie udalo sie zaladowac artykulu.'
  } finally {
    detailLoading.value = false
  }
}

function goBack() {
  selectedArticle.value = null
  detailError.value = ''
}

function setCategory(key: string) {
  activeCategory.value = key
  selectedArticle.value = null
  fetchArticles(key)
}

function renderBody(body: string): { heading: string; text: string }[] {
  const sections: { heading: string; text: string }[] = []
  const parts = body.split('## ')
  for (const part of parts) {
    const trimmed = part.trim()
    if (!trimmed) continue
    const newlineIdx = trimmed.indexOf('\n')
    if (newlineIdx === -1) {
      sections.push({ heading: trimmed, text: '' })
    } else {
      sections.push({
        heading: trimmed.slice(0, newlineIdx).trim(),
        text: trimmed.slice(newlineIdx + 1).trim(),
      })
    }
  }
  return sections
}

onMounted(() => fetchArticles('all'))
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold text-white mb-6">Akademia</h1>

    <!-- Article Detail -->
    <div v-if="selectedArticle || detailLoading || detailError">
      <button
        class="mb-4 text-sm text-blue-400 hover:text-blue-300 transition-colors"
        @click="goBack"
      >
        &larr; Powrot do listy
      </button>

      <LoadingSpinner v-if="detailLoading" />
      <ErrorBox v-else-if="detailError" :message="detailError" />
      <article v-else-if="selectedArticle" class="bg-gray-900 border border-gray-800 rounded-lg p-6">
        <div class="mb-4">
          <span
            class="inline-block text-xs font-medium px-2 py-0.5 rounded-full mb-2"
            :class="getCategoryBadgeClass(selectedArticle.category)"
          >
            {{ selectedArticle.category }}
          </span>
          <h2 class="text-xl font-semibold text-white">{{ selectedArticle.title }}</h2>
        </div>
        <div class="space-y-4">
          <div v-for="(section, idx) in renderBody(selectedArticle.body)" :key="idx">
            <h3 v-if="section.heading" class="text-lg font-semibold text-white mb-1">
              {{ section.heading }}
            </h3>
            <p v-if="section.text" class="text-gray-300 whitespace-pre-line">{{ section.text }}</p>
          </div>
        </div>
      </article>
    </div>

    <!-- Article List -->
    <div v-else>
      <!-- Category Filter -->
      <div class="flex flex-wrap gap-2 mb-6">
        <button
          v-for="cat in categories"
          :key="cat.key"
          class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
          :class="activeCategory === cat.key
            ? 'bg-blue-600 text-white'
            : 'bg-gray-800 text-gray-400 hover:text-gray-200 hover:bg-gray-700'"
          @click="setCategory(cat.key)"
        >
          {{ cat.label }}
        </button>
      </div>

      <LoadingSpinner v-if="loading" />
      <ErrorBox v-else-if="error" :message="error" />
      <div
        v-else-if="articles.length > 0"
        class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
      >
        <div
          v-for="article in articles"
          :key="article.slug"
          class="bg-gray-900 border border-gray-800 rounded-lg p-4 cursor-pointer
                 hover:border-gray-700 hover:bg-gray-800/50 transition-colors"
          @click="selectArticle(article.slug)"
        >
          <span
            class="inline-block text-xs font-medium px-2 py-0.5 rounded-full mb-2"
            :class="getCategoryBadgeClass(article.category)"
          >
            {{ article.category }}
          </span>
          <h3 class="text-white font-semibold mb-1">{{ article.title }}</h3>
          <p class="text-gray-400 text-sm line-clamp-3">{{ article.summary }}</p>
        </div>
      </div>
      <p v-else class="text-gray-500 text-sm">Brak artykulow w tej kategorii.</p>
    </div>
  </div>
</template>
