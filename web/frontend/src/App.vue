<script setup>
import { ref, watch, onMounted } from 'vue'
import { useWebSocket } from './composables/useWebSocket'
import { useBotState } from './composables/useBotState'

import AppHeader from './components/layout/AppHeader.vue'
import Sidebar from './components/layout/Sidebar.vue'
import ControlBar from './components/layout/ControlBar.vue'
import DashboardView from './components/dashboard/DashboardView.vue'
import ProfileSelector from './components/profiles/ProfileSelector.vue'
import SettingsView from './components/settings/SettingsView.vue'
import StatsView from './components/stats/StatsView.vue'
import LogViewer from './components/logs/LogViewer.vue'

// Determine WebSocket URL based on current location
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
const wsUrl = `${wsProtocol}//${window.location.hostname}:8000/ws`

const { isConnected, send, onMessage } = useWebSocket(wsUrl)
const { state, handleMessage, setConnected } = useBotState()

const currentView = ref('dashboard')
const isSidebarOpen = ref(false)

// Handle WebSocket messages
onMessage((message) => {
  handleMessage(message)
})

// Watch connection changes with immediate to catch initial state
watch(isConnected, (connected) => {
  setConnected(connected)
}, { immediate: true })

// Control handlers
function handleStart() {
  send({ type: 'control', data: { action: 'start' } })
}

function handlePause() {
  send({ type: 'control', data: { action: 'pause' } })
}

function handleStop() {
  send({ type: 'control', data: { action: 'stop' } })
}

function handleNavigate(viewId) {
  currentView.value = viewId
  // Close sidebar on mobile after navigation
  isSidebarOpen.value = false
}

function handleProfileChange(profileId) {
  send({ type: 'setting_change', data: { key: 'current_profile', value: profileId } })
}

function handleSettingChange(setting) {
  send({ type: 'setting_change', data: { key: setting.key, value: setting.value } })
}

function toggleSidebar() {
  isSidebarOpen.value = !isSidebarOpen.value
}

function closeSidebar() {
  isSidebarOpen.value = false
}
</script>

<template>
  <div class="min-h-screen bg-gray-900 flex flex-col overflow-x-hidden max-w-full">
    <AppHeader @toggle-sidebar="toggleSidebar" />

    <div class="flex flex-1 overflow-hidden max-w-full">
      <Sidebar
        :is-open="isSidebarOpen"
        @navigate="handleNavigate"
        @close="closeSidebar"
      />

      <main class="flex-1 overflow-y-auto overflow-x-hidden pb-24 md:pb-20 max-w-full">
        <DashboardView v-if="currentView === 'dashboard'" />
        <ProfileSelector v-else-if="currentView === 'profiles'" @profile-change="handleProfileChange" />
        <SettingsView v-else-if="currentView === 'settings'" @setting-change="handleSettingChange" />
        <StatsView v-else-if="currentView === 'stats'" />
        <LogViewer v-else-if="currentView === 'logs'" />

        <!-- Fallback for unknown views -->
        <div v-else class="p-4 md:p-6">
          <h2 class="text-2xl font-bold text-white capitalize">{{ currentView }}</h2>
          <p class="text-gray-400 mt-2">This view is not available.</p>
        </div>
      </main>
    </div>

    <ControlBar
      @start="handleStart"
      @pause="handlePause"
      @stop="handleStop"
      @setting-change="handleSettingChange"
    />
  </div>
</template>
