<script setup>
import { computed } from 'vue'
import { useBotState } from '../../composables/useBotState'
import StatCard from './StatCard.vue'

const { state } = useBotState()

const formattedGold = computed(() => {
  return new Intl.NumberFormat().format(state.gold_looted)
})

const formattedElixir = computed(() => {
  return new Intl.NumberFormat().format(state.elixir_looted)
})

const formattedDE = computed(() => {
  return new Intl.NumberFormat().format(state.de_looted)
})

const recentLogs = computed(() => {
  return state.logs.slice(-5).reverse()
})
</script>

<template>
  <div class="p-4 md:p-6 space-y-4 md:space-y-6">
    <h2 class="text-xl md:text-2xl font-bold text-white">Dashboard</h2>

    <!-- Stats Grid -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
      <StatCard
        title="Bases Attacked"
        :value="state.bases_attacked"
        icon="⚔️"
        color="blue"
      />
      <StatCard
        title="Bases Skipped"
        :value="state.bases_skipped"
        icon="⏭️"
        color="yellow"
      />
      <StatCard
        title="Gold Looted"
        :value="formattedGold"
        icon="🪙"
        color="yellow"
      />
      <StatCard
        title="Elixir Looted"
        :value="formattedElixir"
        icon="💧"
        color="purple"
      />
    </div>

    <!-- Recent Activity -->
    <div class="bg-gray-800 rounded-xl border border-gray-700 p-3 md:p-4">
      <h3 class="text-base md:text-lg font-semibold text-white mb-3 md:mb-4">Recent Activity</h3>
      <div class="space-y-2">
        <div
          v-for="(log, index) in recentLogs"
          :key="index"
          class="text-xs md:text-sm text-gray-300 font-mono bg-gray-900 rounded px-2 md:px-3 py-2 break-all"
        >
          {{ log.message }}
        </div>
        <div v-if="recentLogs.length === 0" class="text-gray-500 text-sm">
          No recent activity
        </div>
      </div>
    </div>
  </div>
</template>
