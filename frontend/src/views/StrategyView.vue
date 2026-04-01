<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import api from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorBox from '../components/ErrorBox.vue'

interface ProfileData {
  name: string
  candidate_buy_threshold: number
  min_confidence: string
  allow_high_risk: boolean
  max_position_pct: number
  stop_loss_pct: number
  take_profit_pct: number
  max_hold_hours: number
  trailing_pct: number
  trailing_arm_pct: number
  break_even_arm_pct: number
  trailing_buy_bounce_pct: number
  trailing_buy_max_hours: number
  slippage_buy_pct: number
  slippage_sell_pct: number
}

interface RegimeData {
  regime: 'risk_on' | 'neutral' | 'risk_off'
  score: number
  signals: Record<string, unknown>
}

interface EffectiveData {
  candidate_buy_threshold: number
  max_position_pct: number
  score_adjustment: number
  position_multiplier: number
  note: string
}

interface AutoSwitchData {
  enabled: boolean
  recommended_profile: string
  reason: string
}

interface StrategySummary {
  profile: ProfileData
  regime: RegimeData
  effective: EffectiveData
  auto_switch: AutoSwitchData
}

const loading = ref(true)
const error = ref('')
const data = ref<StrategySummary | null>(null)

const ALL_PROFILES: ProfileData[] = [
  {
    name: 'conservative',
    candidate_buy_threshold: 68,
    min_confidence: 'high',
    allow_high_risk: false,
    max_position_pct: 0.12,
    stop_loss_pct: -0.05,
    take_profit_pct: 0.10,
    max_hold_hours: 48,
    trailing_pct: 0.03,
    trailing_arm_pct: 0.05,
    break_even_arm_pct: 0.03,
    trailing_buy_bounce_pct: 0.02,
    trailing_buy_max_hours: 12,
    slippage_buy_pct: 0.0005,
    slippage_sell_pct: 0.0005,
  },
  {
    name: 'balanced',
    candidate_buy_threshold: 63,
    min_confidence: 'medium',
    allow_high_risk: false,
    max_position_pct: 0.20,
    stop_loss_pct: -0.08,
    take_profit_pct: 0.15,
    max_hold_hours: 72,
    trailing_pct: 0.05,
    trailing_arm_pct: 0.06,
    break_even_arm_pct: 0.04,
    trailing_buy_bounce_pct: 0.015,
    trailing_buy_max_hours: 18,
    slippage_buy_pct: 0.001,
    slippage_sell_pct: 0.001,
  },
  {
    name: 'aggressive',
    candidate_buy_threshold: 58,
    min_confidence: 'medium',
    allow_high_risk: true,
    max_position_pct: 0.25,
    stop_loss_pct: -0.12,
    take_profit_pct: 0.22,
    max_hold_hours: 96,
    trailing_pct: 0.07,
    trailing_arm_pct: 0.08,
    break_even_arm_pct: 0.05,
    trailing_buy_bounce_pct: 0.01,
    trailing_buy_max_hours: 24,
    slippage_buy_pct: 0.0015,
    slippage_sell_pct: 0.0015,
  },
]

const regimeColor = computed(() => {
  if (!data.value) return ''
  const r = data.value.regime.regime
  if (r === 'risk_on') return 'text-green-400'
  if (r === 'risk_off') return 'text-red-400'
  return 'text-yellow-400'
})

const regimeBg = computed(() => {
  if (!data.value) return ''
  const r = data.value.regime.regime
  if (r === 'risk_on') return 'bg-green-500/10 border-green-500/30'
  if (r === 'risk_off') return 'bg-red-500/10 border-red-500/30'
  return 'bg-yellow-500/10 border-yellow-500/30'
})

const regimeLabel = computed(() => {
  if (!data.value) return ''
  const r = data.value.regime.regime
  if (r === 'risk_on') return 'Risk On'
  if (r === 'risk_off') return 'Risk Off'
  return 'Neutral'
})

const regimeDescription = computed(() => {
  if (!data.value) return ''
  const r = data.value.regime.regime
  if (r === 'risk_on') return 'Rynek sprzyja agresywniejszym pozycjom. Sygnaly wskazuja na trend wzrostowy.'
  if (r === 'risk_off') return 'Rynek w fazie ostroznosci. Zmniejszone pozycje i wyzsze progi wejscia.'
  return 'Rynek w fazie neutralnej. Standardowe parametry strategii.'
})

function pct(v: number): string {
  return (v * 100).toFixed(1) + '%'
}

function pctSigned(v: number): string {
  const val = v * 100
  const sign = val >= 0 ? '+' : ''
  return sign + val.toFixed(1) + '%'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get('/strategy/summary')
    data.value = res.data
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

onMounted(load)

const comparisonRows = [
  { label: 'Prog zakupu', key: 'candidate_buy_threshold', fmt: (v: number) => String(v) },
  { label: 'Min. pewnosc', key: 'min_confidence', fmt: (v: string) => v },
  { label: 'Ryzyko', key: 'allow_high_risk', fmt: (v: boolean) => v ? 'Tak' : 'Nie' },
  { label: 'Max pozycja', key: 'max_position_pct', fmt: pct },
  { label: 'Stop Loss', key: 'stop_loss_pct', fmt: pctSigned },
  { label: 'Take Profit', key: 'take_profit_pct', fmt: pct },
  { label: 'Max czas (h)', key: 'max_hold_hours', fmt: (v: number) => v + 'h' },
  { label: 'Trailing %', key: 'trailing_pct', fmt: pct },
  { label: 'Trailing arm %', key: 'trailing_arm_pct', fmt: pct },
  { label: 'BE arm %', key: 'break_even_arm_pct', fmt: pct },
  { label: 'Bounce %', key: 'trailing_buy_bounce_pct', fmt: pct },
  { label: 'Max godz. entry', key: 'trailing_buy_max_hours', fmt: (v: number) => v + 'h' },
  { label: 'Slippage kupno', key: 'slippage_buy_pct', fmt: pct },
  { label: 'Slippage sprzedaz', key: 'slippage_sell_pct', fmt: pct },
] as const
</script>

<template>
  <div class="space-y-5">
    <h1 class="text-xl font-bold text-white">Strategia</h1>

    <LoadingSpinner v-if="loading" />
    <ErrorBox v-else-if="error" :message="error" />

    <template v-else-if="data">
      <!-- Top row: Regime + Auto Switch -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- Market Regime -->
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h2 class="text-xs text-gray-500 uppercase tracking-wider mb-3">Rezim rynkowy</h2>
          <div class="flex items-center gap-3 mb-2">
            <span
              class="px-3 py-1 rounded-full text-sm font-semibold border"
              :class="regimeBg + ' ' + regimeColor"
            >
              {{ regimeLabel }}
            </span>
            <span class="text-sm text-gray-400 tabular-nums">
              Score: {{ data.regime.score?.toFixed(1) ?? '—' }}
            </span>
          </div>
          <p class="text-xs text-gray-400">{{ regimeDescription }}</p>
        </div>

        <!-- Auto Switch -->
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h2 class="text-xs text-gray-500 uppercase tracking-wider mb-3">Auto Switch</h2>
          <div class="flex items-center gap-3 mb-2">
            <span
              class="px-2 py-0.5 rounded text-xs font-medium"
              :class="data.auto_switch.enabled
                ? 'bg-green-500/10 text-green-400 border border-green-500/30'
                : 'bg-gray-800 text-gray-500 border border-gray-700'"
            >
              {{ data.auto_switch.enabled ? 'Wlaczony' : 'Wylaczony' }}
            </span>
          </div>
          <div class="text-sm text-gray-300">
            Rekomendowany profil:
            <span class="text-white font-medium">{{ data.auto_switch.recommended_profile }}</span>
          </div>
          <div class="text-xs text-gray-500 mt-1">
            Powod: {{ data.auto_switch.reason }}
          </div>
        </div>
      </div>

      <!-- Active Profile -->
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div class="flex items-center gap-3 mb-4">
          <h2 class="text-xs text-gray-500 uppercase tracking-wider">Aktywny profil</h2>
          <span class="px-2 py-0.5 rounded text-xs font-semibold bg-blue-500/20 text-blue-400 border border-blue-500/30">
            {{ data.profile.name }}
          </span>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
          <!-- Entry -->
          <div>
            <h3 class="text-xs text-gray-500 mb-2 font-medium">Wejscie</h3>
            <div class="space-y-1 text-gray-300">
              <div class="flex justify-between"><span>Prog</span><span class="tabular-nums text-white">{{ data.profile.candidate_buy_threshold }}</span></div>
              <div class="flex justify-between"><span>Pewnosc</span><span class="text-white">{{ data.profile.min_confidence }}</span></div>
              <div class="flex justify-between"><span>Ryzyko</span><span class="text-white">{{ data.profile.allow_high_risk ? 'Tak' : 'Nie' }}</span></div>
            </div>
          </div>
          <!-- Position -->
          <div>
            <h3 class="text-xs text-gray-500 mb-2 font-medium">Pozycja</h3>
            <div class="space-y-1 text-gray-300">
              <div class="flex justify-between"><span>Max rozmiar</span><span class="tabular-nums text-white">{{ pct(data.profile.max_position_pct) }}</span></div>
              <div class="flex justify-between"><span>Stop Loss</span><span class="tabular-nums text-red-400">{{ pctSigned(data.profile.stop_loss_pct) }}</span></div>
              <div class="flex justify-between"><span>Take Profit</span><span class="tabular-nums text-green-400">{{ pct(data.profile.take_profit_pct) }}</span></div>
              <div class="flex justify-between"><span>Max czas</span><span class="tabular-nums text-white">{{ data.profile.max_hold_hours }}h</span></div>
            </div>
          </div>
          <!-- Trailing -->
          <div>
            <h3 class="text-xs text-gray-500 mb-2 font-medium">Trailing</h3>
            <div class="space-y-1 text-gray-300">
              <div class="flex justify-between"><span>Trail %</span><span class="tabular-nums text-white">{{ pct(data.profile.trailing_pct) }}</span></div>
              <div class="flex justify-between"><span>Arm %</span><span class="tabular-nums text-white">{{ pct(data.profile.trailing_arm_pct) }}</span></div>
              <div class="flex justify-between"><span>BE arm %</span><span class="tabular-nums text-white">{{ pct(data.profile.break_even_arm_pct) }}</span></div>
            </div>
          </div>
          <!-- Entry Trailing + Slippage -->
          <div>
            <h3 class="text-xs text-gray-500 mb-2 font-medium">Entry Trailing / Slippage</h3>
            <div class="space-y-1 text-gray-300">
              <div class="flex justify-between"><span>Bounce %</span><span class="tabular-nums text-white">{{ pct(data.profile.trailing_buy_bounce_pct) }}</span></div>
              <div class="flex justify-between"><span>Max godz.</span><span class="tabular-nums text-white">{{ data.profile.trailing_buy_max_hours }}h</span></div>
              <div class="flex justify-between"><span>Slip. kupno</span><span class="tabular-nums text-white">{{ pct(data.profile.slippage_buy_pct) }}</span></div>
              <div class="flex justify-between"><span>Slip. sprzedaz</span><span class="tabular-nums text-white">{{ pct(data.profile.slippage_sell_pct) }}</span></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Effective Settings -->
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h2 class="text-xs text-gray-500 uppercase tracking-wider mb-3">Efektywne ustawienia (po korekcie rezimem)</h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div class="bg-gray-800/50 rounded-lg p-3">
            <div class="text-xs text-gray-500 mb-1">Prog zakupu</div>
            <div class="text-white tabular-nums">
              {{ data.profile.candidate_buy_threshold }}
              <span class="text-gray-500 mx-1">&rarr;</span>
              <span class="font-semibold">{{ data.effective.candidate_buy_threshold }}</span>
              <span class="text-xs ml-1" :class="data.effective.score_adjustment > 0 ? 'text-green-400' : data.effective.score_adjustment < 0 ? 'text-red-400' : 'text-gray-500'">
                ({{ data.effective.score_adjustment > 0 ? '-' : '+' }}{{ Math.abs(data.effective.score_adjustment) }} regime adj)
              </span>
            </div>
          </div>
          <div class="bg-gray-800/50 rounded-lg p-3">
            <div class="text-xs text-gray-500 mb-1">Max pozycja</div>
            <div class="text-white tabular-nums">
              {{ pct(data.profile.max_position_pct) }}
              <span class="text-gray-500 mx-1">&rarr;</span>
              <span class="font-semibold">{{ pct(data.effective.max_position_pct) }}</span>
              <span class="text-xs text-gray-400 ml-1">
                (&times;{{ data.effective.position_multiplier.toFixed(2) }})
              </span>
            </div>
          </div>
        </div>
        <p class="text-xs text-gray-500 mt-2">{{ data.effective.note }}</p>
      </div>

      <!-- All Profiles Comparison -->
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h2 class="text-xs text-gray-500 uppercase tracking-wider mb-3">Porownanie profili</h2>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-800">
                <th class="text-left text-gray-500 text-xs py-2 pr-4">Parametr</th>
                <th
                  v-for="p in ALL_PROFILES"
                  :key="p.name"
                  class="text-center text-xs py-2 px-3 capitalize"
                  :class="p.name === data.profile.name ? 'text-blue-400 font-semibold' : 'text-gray-500'"
                >
                  {{ p.name }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in comparisonRows"
                :key="row.key"
                class="border-b border-gray-800/50"
              >
                <td class="text-gray-400 text-xs py-1.5 pr-4">{{ row.label }}</td>
                <td
                  v-for="p in ALL_PROFILES"
                  :key="p.name"
                  class="text-center tabular-nums py-1.5 px-3"
                  :class="p.name === data.profile.name ? 'text-white bg-blue-500/5' : 'text-gray-300'"
                >
                  {{ (row.fmt as (v: any) => string)((p as any)[row.key]) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
