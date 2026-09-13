<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useBotState } from '../../composables/useBotState'

const { state, clearLogs, clearDebugLogs, clearOcrLogs } = useBotState()

const logContainer = ref(null)
const autoScroll = ref(true)
const logType = ref('bot') // 'bot', 'debug', 'ocr'

// Config based on log type
const config = computed(() => {
  switch (logType.value) {
    case 'debug':
      return {
        title: 'Debug Logs',
        subtitle: 'Console output and debug messages',
        logs: state.debugLogs,
        clearFn: clearDebugLogs,
        emptyIcon: '🔧',
        emptyText: 'No debug logs yet',
        emptySubtext: 'Console output will appear here'
      }
    case 'ocr':
      return {
        title: 'OCR Logs',
        subtitle: 'Text recognition readings',
        logs: state.ocrLogs,
        clearFn: clearOcrLogs,
        emptyIcon: '👁️',
        emptyText: 'No OCR logs yet',
        emptySubtext: 'OCR readings will appear when scanning bases'
      }
    default:
      return {
        title: 'Bot Logs',
        subtitle: 'Real-time bot activity and events',
        logs: state.logs,
        clearFn: clearLogs,
        emptyIcon: '📝',
        emptyText: 'No bot logs yet',
        emptySubtext: 'Logs will appear here as the bot runs'
      }
  }
})

// Log level colors
const levelColors = {
  info: 'text-blue-400',
  success: 'text-green-400',
  warning: 'text-yellow-400',
  error: 'text-red-400',
  debug: 'text-gray-400'
}

// Get current logs
const currentLogs = computed(() => config.value.logs)

// Format timestamp for display
function formatTime(timestamp) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
}

// Get color class for log level
function getLevelColor(level) {
  return levelColors[level] || 'text-gray-300'
}

// Auto-scroll to bottom when new logs arrive
watch(
  () => currentLogs.value.length,
  async () => {
    if (autoScroll.value && logContainer.value) {
      await nextTick()
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  }
)

// Scroll to bottom when switching log types
watch(logType, async () => {
  await nextTick()
  scrollToBottom()
})

// Handle manual scroll - disable auto-scroll if user scrolls up
function handleScroll() {
  if (!logContainer.value) return
  const { scrollTop, scrollHeight, clientHeight } = logContainer.value
  autoScroll.value = scrollHeight - scrollTop - clientHeight < 50
}

// Scroll to bottom manually
function scrollToBottom() {
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
    autoScroll.value = true
  }
}

// Handle clear logs
function handleClearLogs() {
  config.value.clearFn()
}

// Initial scroll to bottom
onMounted(() => {
  scrollToBottom()
})
</script>

<template>
  <div class="p-4 md:p-6 h-full flex flex-col">
    <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
      <div>
        <h2 class="text-xl md:text-2xl font-bold text-white">Logs</h2>
        <p class="text-gray-400 text-xs md:text-sm">{{ config.subtitle }}</p>
      </div>

      <div class="flex items-center gap-2 md:gap-3 w-full sm:w-auto">
        <!-- Log Type Selector -->
        <select
          v-model="logType"
          class="flex-1 sm:flex-none bg-gray-700 text-gray-300 rounded-lg px-2 md:px-3 py-2 text-xs md:text-sm border border-gray-600 focus:outline-none focus:border-blue-500 min-h-[44px]"
        >
          <option value="bot">Bot Log</option>
          <option value="debug">Debug</option>
          <option value="ocr">OCR</option>
        </select>

        <!-- Clear Button -->
        <button
          @click="handleClearLogs"
          class="px-3 md:px-4 py-2 bg-gray-700 hover:bg-gray-600 active:bg-gray-600 text-gray-300 rounded-lg text-xs md:text-sm transition-colors min-h-[44px]"
        >
          Clear
        </button>

        <!-- Scroll to Bottom Button -->
        <button
          @click="scrollToBottom"
          class="px-3 md:px-4 py-2 rounded-lg text-xs md:text-sm transition-colors min-h-[44px] whitespace-nowrap"
          :class="autoScroll
            ? 'bg-blue-600 text-white'
            : 'bg-gray-700 hover:bg-gray-600 active:bg-gray-600 text-gray-300'"
        >
          <span class="hidden sm:inline">{{ autoScroll ? 'Auto-scroll ON' : 'Scroll to Bottom' }}</span>
          <span class="sm:hidden">{{ autoScroll ? 'Auto' : 'Bottom' }}</span>
        </button>
      </div>
    </div>

    <!-- Log Container -->
    <div
      ref="logContainer"
      @scroll="handleScroll"
      class="flex-1 bg-gray-900 rounded-xl border border-gray-700 overflow-y-auto font-mono text-xs md:text-sm"
    >
      <!-- Empty State -->
      <div
        v-if="currentLogs.length === 0"
        class="flex items-center justify-center h-full text-gray-500"
      >
        <div class="text-center px-4">
          <div class="text-3xl md:text-4xl mb-3">{{ config.emptyIcon }}</div>
          <p class="text-sm md:text-base">{{ config.emptyText }}</p>
          <p class="text-xs mt-1">{{ config.emptySubtext }}</p>
        </div>
      </div>

      <!-- Log Entries -->
      <div v-else class="p-2 md:p-4 space-y-0.5 md:space-y-1">
        <div
          v-for="(log, index) in currentLogs"
          :key="index"
          class="flex items-start gap-1.5 md:gap-3 py-1 hover:bg-gray-800/50 px-1 md:px-2 -mx-1 md:-mx-2 rounded"
        >
          <!-- Timestamp -->
          <span class="text-gray-500 shrink-0 text-[10px] md:text-xs">
            {{ formatTime(log.timestamp) }}
          </span>

          <!-- Level Badge -->
          <span
            class="shrink-0 text-[9px] md:text-xs uppercase font-medium px-1 md:px-1.5 py-0.5 rounded"
            :class="{
              'bg-blue-500/20 text-blue-400': log.level === 'info',
              'bg-green-500/20 text-green-400': log.level === 'success',
              'bg-yellow-500/20 text-yellow-400': log.level === 'warning',
              'bg-red-500/20 text-red-400': log.level === 'error',
              'bg-gray-500/20 text-gray-400': log.level === 'debug' || !log.level
            }"
          >
            {{ log.level || 'log' }}
          </span>

          <!-- Message -->
          <span
            class="break-all flex-1"
            :class="getLevelColor(log.level)"
          >
            {{ log.message }}
          </span>
        </div>
      </div>
    </div>

    <!-- Footer Stats -->
    <div class="mt-2 md:mt-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 text-xs md:text-sm text-gray-500">
      <div>
        {{ currentLogs.length }} log entries
      </div>
      <div class="flex items-center gap-2">
        <span
          class="w-2 h-2 rounded-full"
          :class="state.connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'"
        ></span>
        {{ state.connected ? 'Live' : 'Disconnected' }}
      </div>
    </div>
  </div>
</template>
