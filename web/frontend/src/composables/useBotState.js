import { reactive, readonly } from 'vue'

// Shared reactive state
const state = reactive({
  // Connection
  connected: false,

  // Bot status
  running: false,
  paused: true,
  status: 'DISCONNECTED',

  // Current profile
  current_profile: 'Farming',

  // Stats
  loop_count: 0,
  bases_attacked: 0,
  bases_skipped: 0,
  gold_looted: 0,
  elixir_looted: 0,
  de_looted: 0,

  // Settings (will be populated from server)
  settings: {},

  // Logs (separate arrays for different log types)
  logs: [],
  debugLogs: [],
  ocrLogs: []
})

// Max logs to keep in memory
const MAX_LOGS = 500
const MAX_DEBUG_LOGS = 1000
const MAX_OCR_LOGS = 500

export function useBotState() {

  function updateState(data) {
    Object.keys(data).forEach(key => {
      if (key in state) {
        state[key] = data[key]
      } else if (key !== 'type') {
        // Store unknown keys in settings
        state.settings[key] = data[key]
      }
    })
  }

  function handleMessage(message) {
    if (message.type === 'state_update') {
      updateState(message.data)
    } else if (message.type === 'log') {
      addLog(message.data)
    } else if (message.type === 'debug_log') {
      addDebugLog(message.data)
    } else if (message.type === 'ocr_log') {
      addOcrLog(message.data)
    } else if (message.type === 'stats_update') {
      updateState(message.data)
    }
  }

  function addLog(logEntry) {
    state.logs.push({
      ...logEntry,
      timestamp: logEntry.timestamp || new Date().toISOString()
    })
    if (state.logs.length > MAX_LOGS) {
      state.logs = state.logs.slice(-MAX_LOGS)
    }
  }

  function addDebugLog(logEntry) {
    state.debugLogs.push({
      ...logEntry,
      timestamp: logEntry.timestamp || new Date().toISOString()
    })
    if (state.debugLogs.length > MAX_DEBUG_LOGS) {
      state.debugLogs = state.debugLogs.slice(-MAX_DEBUG_LOGS)
    }
  }

  function addOcrLog(logEntry) {
    state.ocrLogs.push({
      ...logEntry,
      timestamp: logEntry.timestamp || new Date().toISOString()
    })
    if (state.ocrLogs.length > MAX_OCR_LOGS) {
      state.ocrLogs = state.ocrLogs.slice(-MAX_OCR_LOGS)
    }
  }

  function setConnected(value) {
    state.connected = value
    if (!value) {
      state.status = 'DISCONNECTED'
    }
  }

  function clearLogs() {
    state.logs = []
  }

  function clearDebugLogs() {
    state.debugLogs = []
  }

  function clearOcrLogs() {
    state.ocrLogs = []
  }

  return {
    state: readonly(state),
    updateState,
    handleMessage,
    setConnected,
    addLog,
    addDebugLog,
    addOcrLog,
    clearLogs,
    clearDebugLogs,
    clearOcrLogs
  }
}
