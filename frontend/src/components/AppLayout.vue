<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import SearchBar from './SearchBar.vue'
import { fetchAlertStats } from '../api/alerts'

const route = useRoute()
const unreadAlerts = ref(0)
let badgeTimer: ReturnType<typeof setInterval>

const navItems = [
  { to: '/', label: 'Dashboard', icon: '📊', badge: false },
  { to: '/assets', label: 'Aktywa', icon: '💰', badge: false },
  { to: '/anomalies', label: 'Anomalie', icon: '⚠️', badge: false },
  { to: '/alerts', label: 'Alerty', icon: '🔔', badge: true },
  { to: '/recommendations', label: 'Rekomendacje', icon: '📡', badge: false },
  { to: '/portfolio', label: 'Portfolio', icon: '💼', badge: false },
  { to: '/performance', label: 'Performance', icon: '📈', badge: false },
  { to: '/strategy', label: 'Strategia', icon: '🎯', badge: false },
  { to: '/backtest', label: 'Backtest', icon: '🧪', badge: false },
  { to: '/preset-bots', label: 'Boty', icon: '🤖', badge: false },
  { to: '/watchlists', label: 'Watchlisty', icon: '📋', badge: false },
  { to: '/reports', label: 'Raporty AI', icon: '📄', badge: false },
  { to: '/ingestion', label: 'Data Sync', icon: '🔄', badge: false },
  { to: '/academy', label: 'Akademia', icon: '📚', badge: false },
]

function isActive(path: string): boolean {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

async function refreshBadge() {
  try {
    const stats = await fetchAlertStats()
    unreadAlerts.value = stats.unread_events
  } catch { /* silent */ }
}

onMounted(() => {
  refreshBadge()
  badgeTimer = setInterval(refreshBadge, 60_000)
})

onUnmounted(() => clearInterval(badgeTimer))
</script>

<template>
  <div class="min-h-screen flex">
    <!-- Sidebar -->
    <aside class="w-56 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">
      <div class="p-4 border-b border-gray-800">
        <RouterLink to="/" class="text-lg font-bold text-white tracking-tight">
          MarketPulse<span class="text-blue-400">AI</span>
        </RouterLink>
        <div class="text-xs text-gray-500 mt-0.5">Market Intelligence Platform</div>
      </div>

      <nav class="flex-1 p-3 space-y-1">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors"
          :class="isActive(item.to)
            ? 'bg-gray-800 text-white'
            : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'"
        >
          <span>{{ item.icon }}</span>
          <span>{{ item.label }}</span>
          <span
            v-if="item.badge && unreadAlerts > 0"
            class="ml-auto inline-flex items-center justify-center min-w-5 h-5 rounded-full
                   bg-orange-500/20 text-orange-400 text-xs font-medium px-1.5"
          >
            {{ unreadAlerts }}
          </span>
        </RouterLink>
      </nav>

      <div class="p-3 border-t border-gray-800 text-xs text-gray-600">
        v0.1.0 &middot; Ultra-MVP
      </div>
    </aside>

    <!-- Main -->
    <div class="flex-1 flex flex-col min-w-0">
      <header class="h-14 border-b border-gray-800 flex items-center px-5 gap-4 bg-gray-900/50">
        <SearchBar class="max-w-sm" />
      </header>

      <main class="flex-1 p-5 overflow-auto">
        <RouterView />
      </main>
    </div>
  </div>
</template>
