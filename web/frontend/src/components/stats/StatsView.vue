<script setup>
import { computed } from 'vue'
import { useBotState } from '../../composables/useBotState'

const { state } = useBotState()

// Format numbers with commas
function formatNumber(num) {
  return new Intl.NumberFormat().format(num || 0)
}

// Calculate attack success rate
const attackRate = computed(() => {
  const total = state.bases_attacked + state.bases_skipped
  if (total === 0) return '0%'
  return ((state.bases_attacked / total) * 100).toFixed(1) + '%'
})

// Stats cards data
const statsCards = computed(() => [
  {
    title: 'Total Loops',
    value: formatNumber(state.loop_count),
    icon: '🔄',
    color: 'blue'
  },
  {
    title: 'Bases Attacked',
    value: formatNumber(state.bases_attacked),
    icon: '⚔️',
    color: 'green'
  },
  {
    title: 'Bases Skipped',
    value: formatNumber(state.bases_skipped),
    icon: '⏭️',
    color: 'yellow'
  },
  {
    title: 'Attack Rate',
    value: attackRate.value,
    icon: '📊',
    color: 'purple'
  }
])

const lootStats = computed(() => [
  {
    title: 'Gold Looted',
    value: formatNumber(state.gold_looted),
    icon: '🪙',
    color: 'from-yellow-400 to-yellow-600'
  },
  {
    title: 'Elixir Looted',
    value: formatNumber(state.elixir_looted),
    icon: '💧',
    color: 'from-purple-400 to-purple-600'
  },
  {
    title: 'Dark Elixir Looted',
    value: formatNumber(state.de_looted),
    icon: '🌑',
    color: 'from-gray-400 to-gray-600'
  }
])
</script>

<template>
  <div class="p-4 md:p-6 space-y-4 md:space-y-6">
    <div>
      <h2 class="text-xl md:text-2xl font-bold text-white">Statistics</h2>
      <p class="text-sm md:text-base text-gray-400 mt-1">Track your bot's performance and loot gains.</p>
    </div>

    <!-- Session Stats -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
      <div
        v-for="stat in statsCards"
        :key="stat.title"
        class="bg-gray-800 rounded-xl border border-gray-700 p-3 md:p-4"
      >
        <div class="flex items-center justify-between mb-2">
          <span class="text-gray-400 text-xs md:text-sm">{{ stat.title }}</span>
          <span class="text-xl md:text-2xl">{{ stat.icon }}</span>
        </div>
        <div class="text-lg md:text-2xl font-bold text-white">
          {{ stat.value }}
        </div>
      </div>
    </div>

    <!-- Loot Stats -->
    <div class="bg-gray-800 rounded-xl border border-gray-700 p-4 md:p-6">
      <h3 class="text-base md:text-lg font-semibold text-white mb-3 md:mb-4">Session Loot</h3>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
        <div
          v-for="loot in lootStats"
          :key="loot.title"
          class="text-center"
        >
          <div class="text-3xl md:text-4xl mb-2">{{ loot.icon }}</div>
          <div
            class="text-xl md:text-2xl font-bold bg-gradient-to-r bg-clip-text text-transparent"
            :class="loot.color"
          >
            {{ loot.value }}
          </div>
          <div class="text-xs md:text-sm text-gray-400 mt-1">{{ loot.title }}</div>
        </div>
      </div>
    </div>

    <!-- Charts Coming Soon -->
    <div class="bg-gradient-to-r from-blue-600/20 to-purple-600/20 rounded-xl border border-blue-500/30 p-6 md:p-8">
      <div class="text-center">
        <div class="text-4xl md:text-5xl mb-3 md:mb-4">📈</div>
        <h3 class="text-lg md:text-xl font-semibold text-white">Charts Coming Soon</h3>
        <p class="text-sm md:text-base text-gray-300 mt-2 max-w-md mx-auto">
          Interactive charts for loot history, trophy progression, and attack statistics will be available in a future update.
        </p>
        <div class="mt-4 md:mt-6 flex flex-col sm:flex-row justify-center gap-2 md:gap-4">
          <div class="bg-gray-800/50 rounded-lg px-3 md:px-4 py-2 text-xs md:text-sm text-gray-400">
            Loot over time
          </div>
          <div class="bg-gray-800/50 rounded-lg px-3 md:px-4 py-2 text-xs md:text-sm text-gray-400">
            Trophy history
          </div>
          <div class="bg-gray-800/50 rounded-lg px-3 md:px-4 py-2 text-xs md:text-sm text-gray-400">
            Attack patterns
          </div>
        </div>
      </div>
    </div>

    <!-- Data Files Info -->
    <div class="bg-gray-800 rounded-xl border border-gray-700 p-3 md:p-4">
      <h3 class="text-xs md:text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Data Sources</h3>
      <div class="space-y-2 text-xs md:text-sm">
        <div class="flex items-start gap-2 md:gap-3 text-gray-300">
          <span class="w-2 h-2 bg-green-500 rounded-full mt-1"></span>
          <div class="flex-1 break-all">
            <code class="bg-gray-700 px-2 py-0.5 rounded text-xs">data/loot_tracking.csv</code>
            <span class="text-gray-500 block sm:inline sm:ml-1">- Post-battle rewards</span>
          </div>
        </div>
        <div class="flex items-start gap-2 md:gap-3 text-gray-300">
          <span class="w-2 h-2 bg-blue-500 rounded-full mt-1"></span>
          <div class="flex-1 break-all">
            <code class="bg-gray-700 px-2 py-0.5 rounded text-xs">data/trophy_history.csv</code>
            <span class="text-gray-500 block sm:inline sm:ml-1">- Trophy progression</span>
          </div>
        </div>
        <div class="flex items-start gap-2 md:gap-3 text-gray-300">
          <span class="w-2 h-2 bg-purple-500 rounded-full mt-1"></span>
          <div class="flex-1 break-all">
            <code class="bg-gray-700 px-2 py-0.5 rounded text-xs">data/sbarb_time.csv</code>
            <span class="text-gray-500 block sm:inline sm:ml-1">- SGoblin Farm timing</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
