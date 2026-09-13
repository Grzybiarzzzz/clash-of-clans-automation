<script setup>
import { useBotState } from '../../composables/useBotState'

const { state } = useBotState()

const emit = defineEmits(['toggle-sidebar'])

const statusColors = {
  'RUNNING': 'bg-green-500',
  'PAUSED': 'bg-yellow-500',
  'STOPPED': 'bg-red-500',
  'ATTACKING': 'bg-blue-500',
  'SEARCHING': 'bg-purple-500',
  'DISCONNECTED': 'bg-gray-500'
}
</script>

<template>
  <header class="bg-gray-800 border-b border-gray-700 px-4 md:px-6 py-3 md:py-4 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <!-- Mobile Hamburger Menu -->
      <button
        @click="emit('toggle-sidebar')"
        class="lg:hidden p-2 text-gray-300 hover:text-white hover:bg-gray-700 rounded-lg transition-colors"
        aria-label="Toggle menu"
      >
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      <h1 class="text-lg md:text-xl font-bold text-white">CoC Bot Control</h1>
    </div>

    <div class="flex items-center gap-2 md:gap-4">
      <!-- Status Badge -->
      <div class="flex items-center gap-2">
        <span
          class="w-3 h-3 rounded-full animate-pulse"
          :class="statusColors[state.status] || 'bg-gray-500'"
        ></span>
        <span class="hidden sm:inline text-sm font-medium text-gray-300">{{ state.status }}</span>
      </div>

      <!-- Connection Status -->
      <div class="flex items-center gap-2 text-sm">
        <span
          class="w-2 h-2 rounded-full"
          :class="state.connected ? 'bg-green-400' : 'bg-red-400'"
        ></span>
        <span class="hidden sm:inline text-gray-400">
          {{ state.connected ? 'Connected' : 'Disconnected' }}
        </span>
      </div>
    </div>
  </header>
</template>
