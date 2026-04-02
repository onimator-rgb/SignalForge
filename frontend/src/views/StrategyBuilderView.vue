<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import api from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'

interface RuleForm {
  indicator: string
  operator: string
  value: number | null
  value_upper: number | null
  action: string
  weight: number
  description: string
}

interface StrategyItem {
  id: number
  name: string
  description: string
  rules: unknown[]
  profile_name: string
  created_at: string
}

const INDICATORS = ['rsi', 'macd_histogram', 'bollinger_pct_b', 'price_change_pct', 'volume_change_pct']
const OPERATORS = ['gt', 'gte', 'lt', 'lte', 'eq', 'between']
const ACTIONS = ['buy', 'sell', 'hold']
const PROFILES = ['balanced', 'aggressive', 'conservative']

const OPERATOR_LABELS: Record<string, string> = {
  gt: '>', gte: '>=', lt: '<', lte: '<=', eq: '=', between: 'between',
}

const ACTION_COLORS: Record<string, string> = {
  buy: 'text-green-400',
  sell: 'text-red-400',
  hold: 'text-yellow-400',
}

// Form state
const name = ref('')
const description = ref('')
const profileName = ref('balanced')
const rules = ref<RuleForm[]>([])
const saving = ref(false)
const saveError = ref('')
const saveSuccess = ref('')

// Strategies list state
const strategies = ref<StrategyItem[]>([])
const listLoading = ref(true)
const listError = ref('')

const canSave = computed(() => name.value.trim().length > 0 && rules.value.length > 0 && !saving.value)

function createBlankRule(): RuleForm {
  return {
    indicator: 'rsi',
    operator: 'gt',
    value: null,
    value_upper: null,
    action: 'buy',
    weight: 1.0,
    description: '',
  }
}

function addRule() {
  rules.value.push(createBlankRule())
}

function removeRule(index: number) {
  rules.value.splice(index, 1)
}

async function saveStrategy() {
  saving.value = true
  saveError.value = ''
  saveSuccess.value = ''

  const payload = {
    name: name.value.trim(),
    description: description.value.trim(),
    profile_name: profileName.value,
    rules: rules.value.map((r) => ({
      condition: {
        indicator: r.indicator,
        operator: r.operator,
        value: r.value,
        ...(r.operator === 'between' ? { value_upper: r.value_upper } : {}),
      },
      action: {
        action: r.action,
        weight: r.weight,
      },
      description: r.description || undefined,
    })),
  }

  try {
    await api.post('/strategies/', payload)
    saveSuccess.value = 'Strategy saved successfully!'
    name.value = ''
    description.value = ''
    profileName.value = 'balanced'
    rules.value = []
    await loadStrategies()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    saveError.value = err.response?.data?.detail || 'Failed to save strategy'
  } finally {
    saving.value = false
    setTimeout(() => { saveSuccess.value = ''; saveError.value = '' }, 4000)
  }
}

async function loadStrategies() {
  listLoading.value = true
  listError.value = ''
  try {
    const res = await api.get('/strategies/')
    strategies.value = Array.isArray(res.data) ? res.data : res.data.items ?? []
  } catch {
    listError.value = 'Failed to load strategies'
  } finally {
    listLoading.value = false
  }
}

async function deleteStrategy(id: number) {
  try {
    await api.delete(`/strategies/${id}`)
    await loadStrategies()
  } catch {
    listError.value = 'Failed to delete strategy'
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('pl-PL', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

onMounted(() => {
  loadStrategies()
})
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-xl font-semibold text-gray-100">Strategy Builder</h1>

    <!-- Create Strategy Form -->
    <div class="bg-gray-800 rounded-lg border border-gray-700 p-5 space-y-4">
      <h2 class="text-lg font-medium text-gray-100">Create Strategy</h2>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label class="block text-sm text-gray-400 mb-1">Name *</label>
          <input
            v-model="name"
            type="text"
            maxlength="100"
            placeholder="Strategy name"
            class="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100
                   focus:border-blue-500 focus:outline-none placeholder-gray-600"
          />
        </div>
        <div>
          <label class="block text-sm text-gray-400 mb-1">Description</label>
          <input
            v-model="description"
            type="text"
            placeholder="Optional description"
            class="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100
                   focus:border-blue-500 focus:outline-none placeholder-gray-600"
          />
        </div>
        <div>
          <label class="block text-sm text-gray-400 mb-1">Profile</label>
          <select
            v-model="profileName"
            class="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100
                   focus:border-blue-500 focus:outline-none"
          >
            <option v-for="p in PROFILES" :key="p" :value="p">{{ p }}</option>
          </select>
        </div>
      </div>

      <!-- Rules -->
      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-medium text-gray-300">Rules ({{ rules.length }})</h3>
          <button
            @click="addRule"
            class="text-sm text-blue-400 hover:text-blue-300 transition-colors"
          >
            + Add Rule
          </button>
        </div>

        <div v-if="rules.length === 0" class="text-sm text-gray-500 py-4 text-center">
          No rules yet. Click "+ Add Rule" to start building your strategy.
        </div>

        <div
          v-for="(rule, idx) in rules"
          :key="idx"
          class="bg-gray-900 border border-gray-700 rounded-lg p-4 space-y-3"
        >
          <div class="flex items-center justify-between">
            <span class="text-xs font-medium text-gray-500 uppercase tracking-wider">Rule {{ idx + 1 }}</span>
            <button
              @click="removeRule(idx)"
              class="text-red-400 hover:text-red-300 text-sm font-bold transition-colors"
              title="Remove rule"
            >
              X
            </button>
          </div>

          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div>
              <label class="block text-xs text-gray-500 mb-1">Indicator</label>
              <select
                v-model="rule.indicator"
                class="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-100
                       focus:border-blue-500 focus:outline-none"
              >
                <option v-for="ind in INDICATORS" :key="ind" :value="ind">{{ ind }}</option>
              </select>
            </div>
            <div>
              <label class="block text-xs text-gray-500 mb-1">Operator</label>
              <select
                v-model="rule.operator"
                class="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-100
                       focus:border-blue-500 focus:outline-none"
              >
                <option v-for="op in OPERATORS" :key="op" :value="op">
                  {{ OPERATOR_LABELS[op] }} ({{ op }})
                </option>
              </select>
            </div>
            <div>
              <label class="block text-xs text-gray-500 mb-1">Value</label>
              <input
                v-model.number="rule.value"
                type="number"
                step="any"
                class="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-100
                       tabular-nums focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div v-if="rule.operator === 'between'">
              <label class="block text-xs text-gray-500 mb-1">Value Upper</label>
              <input
                v-model.number="rule.value_upper"
                type="number"
                step="any"
                class="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-100
                       tabular-nums focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>

          <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
            <div>
              <label class="block text-xs text-gray-500 mb-1">Action</label>
              <select
                v-model="rule.action"
                class="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-100
                       focus:border-blue-500 focus:outline-none"
              >
                <option v-for="a in ACTIONS" :key="a" :value="a">{{ a }}</option>
              </select>
            </div>
            <div>
              <label class="block text-xs text-gray-500 mb-1">Weight (0-2)</label>
              <input
                v-model.number="rule.weight"
                type="number"
                min="0"
                max="2"
                step="0.1"
                class="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-100
                       tabular-nums focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label class="block text-xs text-gray-500 mb-1">Description</label>
              <input
                v-model="rule.description"
                type="text"
                placeholder="Optional"
                class="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-100
                       focus:border-blue-500 focus:outline-none placeholder-gray-600"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- Save button + feedback -->
      <div class="flex items-center gap-3">
        <button
          @click="saveStrategy"
          :disabled="!canSave"
          class="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed
                 text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors"
        >
          {{ saving ? 'Saving...' : 'Save Strategy' }}
        </button>
        <span v-if="saveSuccess" class="text-sm text-green-400">{{ saveSuccess }}</span>
        <span v-if="saveError" class="text-sm text-red-400">{{ saveError }}</span>
      </div>
    </div>

    <!-- Existing Strategies -->
    <div class="space-y-3">
      <h2 class="text-lg font-medium text-gray-100">Existing Strategies</h2>

      <LoadingSpinner v-if="listLoading" />
      <ErrorBox v-else-if="listError" :message="listError" />
      <div v-else-if="strategies.length === 0" class="text-sm text-gray-500">
        No strategies found.
      </div>
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div
          v-for="s in strategies"
          :key="s.id"
          class="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-2"
        >
          <div class="flex items-start justify-between">
            <h3 class="text-sm font-medium text-gray-100">{{ s.name }}</h3>
            <button
              @click="deleteStrategy(s.id)"
              class="text-red-400 hover:text-red-300 text-xs font-bold transition-colors"
              title="Delete strategy"
            >
              X
            </button>
          </div>
          <p v-if="s.description" class="text-xs text-gray-400">{{ s.description }}</p>
          <div class="flex items-center gap-3 text-xs text-gray-500">
            <span>{{ s.rules?.length ?? 0 }} rules</span>
            <span class="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400">{{ s.profile_name }}</span>
          </div>
          <div class="text-xs text-gray-600 tabular-nums">{{ formatDate(s.created_at) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>
