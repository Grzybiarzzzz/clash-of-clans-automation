<script setup>
import { ref } from 'vue'
import { useBotState } from '../../composables/useBotState'

const { state } = useBotState()

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['navigate', 'close'])

const currentView = ref('dashboard')

const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
  { id: 'profiles', label: 'Profiles', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
  { id: 'settings', label: 'Settings', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
  { id: 'stats', label: 'Statistics', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
  { id: 'logs', label: 'Logs', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' }
]

function navigate(viewId) {
  currentView.value = viewId
  emit('navigate', viewId)
}
</script>

<template>
  <!-- Mobile Overlay - use v-if to completely remove from DOM when closed -->
  <div
    v-if="isOpen"
    @click="emit('close')"
    class="lg:hidden fixed inset-0 bg-black bg-opacity-50 z-40 transition-opacity"
  ></div>

  <!-- Sidebar -->
  <aside
    class="fixed lg:static inset-y-0 left-0 z-50 w-64 lg:w-48 bg-gray-800 border-r border-gray-700 p-4 transform transition-transform duration-300 ease-in-out"
    :class="[
      isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
      !isOpen ? 'pointer-events-none lg:pointer-events-auto' : ''
    ]"
  >
    <!-- Mobile Close Button -->
    <div class="lg:hidden flex justify-end mb-4">
      <button
        @click="emit('close')"
        class="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-colors"
        aria-label="Close menu"
      >
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <nav class="space-y-1">
      <button
        v-for="item in navItems"
        :key="item.id"
        @click="navigate(item.id)"
        class="w-full flex items-center gap-3 px-4 py-3 lg:px-3 lg:py-2 rounded-lg text-left transition-colors text-base lg:text-sm"
        :class="currentView === item.id
          ? 'bg-blue-600 text-white'
          : 'text-gray-300 hover:bg-gray-700'"
      >
        <svg
          class="w-6 h-6 lg:w-5 lg:h-5 flex-shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            :d="item.icon"
          />
        </svg>
        <span>{{ item.label }}</span>
      </button>
    </nav>
  </aside>
</template>
