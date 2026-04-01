<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'

interface PresetParamSchema {
  name: string
  type: string
  description: string
  default: number | null
}

interface PresetInfo {
  preset_type: string
  display_name: string
  description: string
  params: PresetParamSchema[]
}

interface GenerateResponse {
  preset_type: string
  rules: Record<string, unknown>[]
  num_rules: number
}

type ViewState = 'list' | 'form' | 'results'

const state = ref<ViewState>('list')
const loading = ref(true)
const submitting = ref(false)
const error = ref('')
const presets = ref<PresetInfo[]>([])
const selectedPreset = ref<PresetInfo | null>(null)
const paramValues = ref<Record<string, number | string>>({})
const generatedRules = ref<GenerateResponse | null>(null)

const presetColors: Record<string, { border: string; bg: string; text: string; hover: string }> = {
  grid: {
    border: 'border-blue-500',
    bg: 'bg-blue-500/10',
    text: 'text-blue-400',
    hover: 'hover:border-blue-500',
  },
  dca: {
    border: 'border-green-500',
    bg: 'bg-green-500/10',
    text: 'text-green-400',
    hover: 'hover:border-green-500',
  },
  btd: {
    border: 'border-purple-500',
    bg: 'bg-purple-500/10',
    text: 'text-purple-400',
    hover: 'hover:border-purple-500',
  },
}

function getColors(presetType: string) {
  const key = presetType.toLowerCase()
  return presetColors[key] || presetColors.grid
}

async function loadPresets() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get<PresetInfo[]>('/strategies/presets')
    presets.value = res.data
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    error.value = err.response?.data?.detail || err.message || 'Blad ladowania presetow'
  } finally {
    loading.value = false
  }
}

function selectPreset(preset: PresetInfo) {
  selectedPreset.value = preset
  paramValues.value = {}
  for (const p of preset.params) {
    paramValues.value[p.name] = p.default ?? 0
  }
  state.value = 'form'
}

async function generateRules() {
  if (!selectedPreset.value) return
  submitting.value = true
  error.value = ''
  try {
    const res = await api.post<GenerateResponse>('/strategies/from-preset', {
      preset_type: selectedPreset.value.preset_type,
      params: paramValues.value,
    })
    generatedRules.value = res.data
    state.value = 'results'
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    error.value = err.response?.data?.detail || err.message || 'Blad generowania regul'
  } finally {
    submitting.value = false
  }
}

function goBack() {
  if (state.value === 'results') {
    state.value = 'form'
    generatedRules.value = null
  } else {
    state.value = 'list'
    selectedPreset.value = null
  }
  error.value = ''
}

function inputStep(paramType: string): string {
  return paramType === 'int' ? '1' : 'any'
}

onMounted(loadPresets)
</script>

<template>
  <div class="space-y-5">
    <div class="flex items-center gap-3">
      <button
        v-if="state !== 'list'"
        class="text-gray-400 hover:text-white transition-colors"
        @click="goBack"
      >
        ← Wstecz
      </button>
      <h1 class="text-xl font-bold text-white">Preset Boty</h1>
    </div>

    <LoadingSpinner v-if="loading" />
    <ErrorBox v-else-if="error" :message="error" />

    <!-- Preset list -->
    <template v-else-if="state === 'list'">
      <p class="text-sm text-gray-400">
        Wybierz typ bota, skonfiguruj parametry i wygeneruj reguly strategii.
      </p>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <button
          v-for="preset in presets"
          :key="preset.preset_type"
          class="bg-gray-800 border border-gray-700 rounded-lg p-5 text-left transition-colors"
          :class="getColors(preset.preset_type).hover"
          @click="selectPreset(preset)"
        >
          <div class="flex items-center gap-2 mb-2">
            <span
              class="px-2 py-0.5 rounded text-xs font-semibold"
              :class="[getColors(preset.preset_type).bg, getColors(preset.preset_type).text]"
            >
              {{ preset.preset_type.toUpperCase() }}
            </span>
          </div>
          <h3 class="text-white font-medium mb-1">{{ preset.display_name }}</h3>
          <p class="text-sm text-gray-400 mb-3">{{ preset.description }}</p>
          <div class="text-xs text-gray-500">
            {{ preset.params.length }} {{ preset.params.length === 1 ? 'parametr' : 'parametrow' }}
          </div>
        </button>
      </div>
    </template>

    <!-- Parameter form -->
    <template v-else-if="state === 'form' && selectedPreset">
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <div class="flex items-center gap-2 mb-4">
          <span
            class="px-2 py-0.5 rounded text-xs font-semibold"
            :class="[getColors(selectedPreset.preset_type).bg, getColors(selectedPreset.preset_type).text]"
          >
            {{ selectedPreset.preset_type.toUpperCase() }}
          </span>
          <h2 class="text-lg font-semibold text-white">{{ selectedPreset.display_name }}</h2>
        </div>
        <p class="text-sm text-gray-400 mb-5">{{ selectedPreset.description }}</p>

        <form class="space-y-4" @submit.prevent="generateRules">
          <div
            v-for="param in selectedPreset.params"
            :key="param.name"
            class="space-y-1"
          >
            <label :for="'param-' + param.name" class="block text-sm font-medium text-gray-300">
              {{ param.name }}
            </label>
            <p class="text-xs text-gray-500">{{ param.description }}</p>
            <input
              :id="'param-' + param.name"
              v-model.number="paramValues[param.name]"
              type="number"
              :step="inputStep(param.type)"
              class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white
                     focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>

          <button
            type="submit"
            :disabled="submitting"
            class="px-4 py-2 rounded-lg text-sm font-medium transition-colors
                   bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ submitting ? 'Generowanie...' : 'Generuj reguly' }}
          </button>
        </form>
      </div>
    </template>

    <!-- Rules output -->
    <template v-else-if="state === 'results' && generatedRules">
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold text-white">Wygenerowane reguly</h2>
          <span class="text-sm text-gray-400">
            {{ generatedRules.num_rules }} {{ generatedRules.num_rules === 1 ? 'regula' : 'regul' }}
          </span>
        </div>

        <div class="space-y-3">
          <div
            v-for="(rule, idx) in generatedRules.rules"
            :key="idx"
            class="bg-gray-800 border border-gray-700 rounded-lg p-4"
          >
            <div v-if="rule.description" class="text-sm font-medium text-white mb-2">
              {{ rule.description }}
            </div>
            <div v-if="rule.conditions" class="text-xs text-gray-400 mb-1">
              <span class="text-gray-500 font-medium">Warunki:</span>
              {{ typeof rule.conditions === 'string' ? rule.conditions : JSON.stringify(rule.conditions) }}
            </div>
            <div v-if="rule.action" class="text-xs text-gray-400">
              <span class="text-gray-500 font-medium">Akcja:</span>
              {{ typeof rule.action === 'string' ? rule.action : JSON.stringify(rule.action) }}
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
