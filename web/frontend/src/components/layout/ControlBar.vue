<script setup>
import { ref, computed } from 'vue'
import { useBotState } from '../../composables/useBotState'

const { state } = useBotState()

const emit = defineEmits(['start', 'pause', 'stop', 'setting-change'])

// Start menu state
const showStartMenu = ref(false)

// Available profiles
const mainBaseProfiles = ['Farming', 'SBarb Farm', 'SGoblin Farm', 'Achievement Farm', 'Custom']
const builderBaseProfiles = ['BB Elixir', 'BB Gold']
const deprecatedProfiles = ['Trophy Push', 'Derank']

// Current profile from state
const currentProfile = computed(() => state.current_profile || 'Farming')

// Auto-pause settings from state
const autoPauseMode = computed(() => state.settings?.auto_pause_mode ?? 'manual')
const autoPauseValue = computed(() => state.settings?.auto_pause_value ?? 50)
const storageFullGold = computed(() => state.settings?.storage_full_gold ?? true)
const storageFullElixir = computed(() => state.settings?.storage_full_elixir ?? true)
const storageFullDE = computed(() => state.settings?.storage_full_de ?? false)
const storageFullPreset = computed(() => state.settings?.storage_full_preset ?? 'main')
const activeStoragePreset = computed(() => state.settings?.active_storage_preset ?? 'main')
const storagePresets = computed(() => {
  const presets = state.settings?.storage_presets
  return presets ? Object.keys(presets) : ['main', 'alt']
})

// Queue settings from state
const queueEnabled = computed(() => state.settings?.queue_enabled ?? false)
const queueMode = computed(() => state.settings?.queue_mode ?? 'smart')
const smartMainMode = computed(() => state.settings?.smart_mode_config?.main_base_mode ?? 'SBarb Farm')

function toggleStartMenu() {
  if (!state.running) {
    showStartMenu.value = !showStartMenu.value
  }
}

function closeStartMenu() {
  showStartMenu.value = false
}

function updateSetting(key, value) {
  emit('setting-change', { key, value })
}

function selectProfileAndStart(profile) {
  updateSetting('current_profile', profile)
  showStartMenu.value = false
  emit('start')
}

function startWithCurrentSettings() {
  showStartMenu.value = false
  emit('start')
}

// Get profile icon
function getProfileIcon(profile) {
  const icons = {
    'Farming': '🌾',
    'SBarb Farm': '⚔️',
    'SGoblin Farm': '👺',
    'Achievement Farm': '🏆',
    'Custom': '⚙️',
    'BB Elixir': '💧',
    'BB Gold': '🪙',
    'Trophy Push': '🏅',
    'Derank': '📉'
  }
  return icons[profile] || '📋'
}

// Get display text for current auto-pause mode
const currentModeText = computed(() => {
  switch (autoPauseMode.value) {
    case 'storage_full':
      const resources = []
      if (storageFullGold.value) resources.push('Gold')
      if (storageFullElixir.value) resources.push('Elixir')
      if (storageFullDE.value) resources.push('DE')
      return `Storage Full (${resources.join(', ') || 'None'})`
    case 'loops':
      return `After ${autoPauseValue.value} attacks`
    case 'minutes':
      return `After ${autoPauseValue.value} min`
    default:
      return 'Manual'
  }
})
</script>

<template>
  <footer class="fixed bottom-0 left-0 lg:left-48 right-0 bg-gray-800 border-t border-gray-700 px-3 md:px-6 py-3 md:py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] z-50 relative">
    <!-- Start Menu Overlay -->
    <div
      v-if="showStartMenu"
      class="fixed inset-0 z-40"
      @click="closeStartMenu"
    ></div>

    <!-- Start Menu Dropdown -->
    <div
      v-if="showStartMenu"
      class="fixed bottom-20 left-3 lg:left-52 w-80 bg-gray-700 rounded-lg shadow-xl border border-gray-600 z-[100] max-h-[70vh] overflow-y-auto"
    >
      <!-- Header -->
      <div class="p-3 border-b border-gray-600 bg-gray-700">
        <div class="text-sm font-medium text-white">Start Options</div>
        <div class="text-xs text-gray-400 mt-0.5">Configure and start</div>
      </div>

      <!-- Queue System -->
      <div class="p-2 border-b border-gray-600">
        <div class="flex items-center justify-between mb-2">
          <div class="text-xs text-gray-500 font-medium">Queue System</div>
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              :checked="queueEnabled"
              @change="updateSetting('queue_enabled', $event.target.checked)"
              class="w-4 h-4 rounded border-gray-500 text-blue-500"
            />
            <span class="text-xs text-gray-400">Enable</span>
          </label>
        </div>
        <div v-if="queueEnabled" class="space-y-2">
          <div class="flex gap-2">
            <button
              @click="updateSetting('queue_mode', 'smart')"
              class="flex-1 px-3 py-1.5 rounded text-xs font-medium transition-colors"
              :class="queueMode === 'smart' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-600'"
            >
              Smart
            </button>
            <button
              @click="updateSetting('queue_mode', 'manual')"
              class="flex-1 px-3 py-1.5 rounded text-xs font-medium transition-colors"
              :class="queueMode === 'manual' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-600'"
            >
              Manual
            </button>
          </div>
          <div class="flex items-center gap-2 mt-2">
            <span class="text-xs text-gray-500">Storage Preset:</span>
            <select
              :value="activeStoragePreset"
              @change="updateSetting('active_storage_preset', $event.target.value)"
              class="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-white focus:border-blue-500 focus:outline-none"
            >
              <option v-for="preset in storagePresets" :key="preset" :value="preset">
                {{ preset }}
              </option>
            </select>
          </div>
          <div class="text-xs text-gray-500 px-1">
            <span v-if="queueMode === 'smart'">Starts with {{ smartMainMode }} → BB when full</span>
            <span v-else>Configure schedule in Settings tab</span>
          </div>
        </div>
      </div>

      <!-- Profile Selection (only when queue disabled) -->
      <div v-if="!queueEnabled" class="p-2 border-b border-gray-600">
        <div class="text-xs text-gray-500 px-2 py-1 font-medium">Profile</div>
        <select
          :value="currentProfile"
          @change="updateSetting('current_profile', $event.target.value)"
          class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
        >
          <optgroup label="Main Base">
            <option v-for="profile in mainBaseProfiles" :key="profile" :value="profile">
              {{ profile }}
            </option>
          </optgroup>
          <optgroup label="Builder Base">
            <option v-for="profile in builderBaseProfiles" :key="profile" :value="profile">
              {{ profile }}
            </option>
          </optgroup>
        </select>
      </div>

      <!-- Auto-Pause Options (only when queue disabled) -->
      <div v-if="!queueEnabled" class="p-2 space-y-1">
        <div class="text-xs text-gray-500 px-2 py-1 font-medium">Auto-Pause Mode</div>

        <!-- Manual -->
        <button
          @click="updateSetting('auto_pause_mode', 'manual')"
          class="w-full text-left px-3 py-2 rounded-lg transition-colors flex items-center gap-3"
          :class="autoPauseMode === 'manual' ? 'bg-blue-600/20 text-blue-400' : 'hover:bg-gray-600 text-gray-300'"
        >
          <span class="w-2 h-2 rounded-full" :class="autoPauseMode === 'manual' ? 'bg-blue-400' : 'bg-gray-500'"></span>
          <div>
            <div class="font-medium text-sm">Manual</div>
            <div class="text-xs text-gray-500">No automatic pause</div>
          </div>
        </button>

        <!-- Storage Full -->
        <div class="rounded-lg transition-colors" :class="autoPauseMode === 'storage_full' ? 'bg-blue-600/20' : ''">
          <button
            @click="updateSetting('auto_pause_mode', 'storage_full')"
            class="w-full text-left px-3 py-2 flex items-center gap-3"
            :class="autoPauseMode === 'storage_full' ? 'text-blue-400' : 'hover:bg-gray-600 text-gray-300 rounded-lg'"
          >
            <span class="w-2 h-2 rounded-full" :class="autoPauseMode === 'storage_full' ? 'bg-blue-400' : 'bg-gray-500'"></span>
            <div>
              <div class="font-medium text-sm">Storage Full</div>
              <div class="text-xs text-gray-500">Pause when resources full</div>
            </div>
          </button>
          <div v-if="autoPauseMode === 'storage_full'" class="space-y-2 px-3 pb-2 ml-5">
            <div class="flex gap-3">
              <label class="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  :checked="storageFullGold"
                  @change="updateSetting('storage_full_gold', $event.target.checked)"
                  class="w-3.5 h-3.5 rounded border-gray-500 text-yellow-500"
                />
                <span class="text-xs text-gray-400">Gold</span>
              </label>
              <label class="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  :checked="storageFullElixir"
                  @change="updateSetting('storage_full_elixir', $event.target.checked)"
                  class="w-3.5 h-3.5 rounded border-gray-500 text-purple-500"
                />
                <span class="text-xs text-gray-400">Elixir</span>
              </label>
              <label class="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  :checked="storageFullDE"
                  @change="updateSetting('storage_full_de', $event.target.checked)"
                  class="w-3.5 h-3.5 rounded border-gray-500 text-gray-400"
                />
                <span class="text-xs text-gray-400">DE</span>
              </label>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-xs text-gray-500">Preset:</span>
              <select
                :value="storageFullPreset"
                @change="updateSetting('storage_full_preset', $event.target.value)"
                class="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-white focus:border-blue-500 focus:outline-none"
              >
                <option v-for="preset in storagePresets" :key="preset" :value="preset">
                  {{ preset }}
                </option>
              </select>
            </div>
          </div>
        </div>

        <!-- After X Attacks -->
        <button
          @click="updateSetting('auto_pause_mode', 'loops')"
          class="w-full text-left px-3 py-2 rounded-lg transition-colors flex items-center gap-3"
          :class="autoPauseMode === 'loops' ? 'bg-blue-600/20 text-blue-400' : 'hover:bg-gray-600 text-gray-300'"
        >
          <span class="w-2 h-2 rounded-full" :class="autoPauseMode === 'loops' ? 'bg-blue-400' : 'bg-gray-500'"></span>
          <div class="flex items-center gap-2 text-sm">
            <span class="font-medium">After</span>
            <input
              type="number"
              :value="autoPauseValue"
              @input="updateSetting('auto_pause_value', parseInt($event.target.value) || 50)"
              @click.stop
              min="1"
              max="1000"
              class="w-14 bg-gray-800 border border-gray-500 rounded px-2 py-1 text-white text-sm focus:border-blue-500 focus:outline-none"
            />
            <span class="font-medium">attacks</span>
          </div>
        </button>

        <!-- After X Minutes -->
        <button
          @click="updateSetting('auto_pause_mode', 'minutes')"
          class="w-full text-left px-3 py-2 rounded-lg transition-colors flex items-center gap-3"
          :class="autoPauseMode === 'minutes' ? 'bg-blue-600/20 text-blue-400' : 'hover:bg-gray-600 text-gray-300'"
        >
          <span class="w-2 h-2 rounded-full" :class="autoPauseMode === 'minutes' ? 'bg-blue-400' : 'bg-gray-500'"></span>
          <div class="flex items-center gap-2 text-sm">
            <span class="font-medium">After</span>
            <input
              type="number"
              :value="autoPauseValue"
              @input="updateSetting('auto_pause_value', parseInt($event.target.value) || 60)"
              @click.stop
              min="1"
              max="1440"
              class="w-14 bg-gray-800 border border-gray-500 rounded px-2 py-1 text-white text-sm focus:border-blue-500 focus:outline-none"
            />
            <span class="font-medium">minutes</span>
          </div>
        </button>
      </div>

      <!-- Start Button -->
      <div class="p-2 border-t border-gray-600 bg-gray-700">
        <button
          @click="startWithCurrentSettings"
          class="w-full px-3 py-2.5 bg-green-600 hover:bg-green-500 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd" />
          </svg>
          <span v-if="queueEnabled">Start Queue ({{ smartMainMode }})</span>
          <span v-else>Start {{ currentProfile }}</span>
        </button>
      </div>
    </div>

    <!-- Mobile Layout: Vertical Stacked Buttons -->
    <div class="flex flex-col md:hidden gap-2">
      <div class="flex gap-2">
        <!-- Start Button with dropdown -->
        <button
          @click="toggleStartMenu"
          :disabled="state.running"
          class="flex-1 min-h-[50px] px-4 py-3 rounded-lg font-semibold transition-colors flex items-center justify-center gap-2 text-base"
          :class="state.running
            ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
            : 'bg-green-600 hover:bg-green-500 active:bg-green-700 text-white'"
        >
          <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd" />
          </svg>
          Start
          <svg class="w-4 h-4 ml-1" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
          </svg>
        </button>

        <!-- Pause/Resume Button -->
        <button
          @click="emit('pause')"
          :disabled="!state.running"
          class="flex-1 min-h-[50px] px-4 py-3 rounded-lg font-semibold transition-colors flex items-center justify-center gap-2 text-base"
          :class="!state.running
            ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
            : state.paused
              ? 'bg-green-600 hover:bg-green-500 active:bg-green-700 text-white'
              : 'bg-yellow-600 hover:bg-yellow-500 active:bg-yellow-700 text-white'"
        >
          <svg v-if="!state.paused" class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" />
          </svg>
          <svg v-else class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd" />
          </svg>
          {{ state.paused ? 'Resume' : 'Pause' }}
        </button>

        <!-- Stop Button -->
        <button
          @click="emit('stop')"
          :disabled="!state.running"
          class="flex-1 min-h-[50px] px-4 py-3 rounded-lg font-semibold transition-colors flex items-center justify-center gap-2 text-base"
          :class="!state.running
            ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
            : 'bg-red-600 hover:bg-red-500 active:bg-red-700 text-white'"
        >
          <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clip-rule="evenodd" />
          </svg>
          Stop
        </button>
      </div>

      <!-- Mobile Stats Row -->
      <div class="flex items-center justify-around text-xs text-gray-300 px-2">
        <div>
          <span class="text-gray-500">Loop:</span>
          <span class="ml-1 font-mono">{{ state.loop_count }}</span>
        </div>
        <div class="text-gray-600">|</div>
        <div class="truncate max-w-[150px]">
          <span v-if="queueEnabled" class="text-blue-400">Queue: {{ queueMode }}</span>
          <span v-else><span class="text-gray-500">Profile:</span> {{ currentProfile }}</span>
        </div>
      </div>
    </div>

    <!-- Desktop Layout: Horizontal -->
    <div class="hidden md:flex items-center justify-between">
      <div class="flex items-center gap-3">
        <!-- Start Button with dropdown -->
        <button
          @click="toggleStartMenu"
          :disabled="state.running"
          class="min-h-[44px] px-5 py-2.5 rounded-lg font-medium transition-colors flex items-center gap-2"
          :class="state.running
            ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
            : 'bg-green-600 hover:bg-green-500 text-white'"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd" />
          </svg>
          Start
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
          </svg>
        </button>

        <!-- Pause/Resume Button -->
        <button
          @click="emit('pause')"
          :disabled="!state.running"
          class="min-h-[44px] px-5 py-2.5 rounded-lg font-medium transition-colors flex items-center gap-2"
          :class="!state.running
            ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
            : state.paused
              ? 'bg-green-600 hover:bg-green-500 text-white'
              : 'bg-yellow-600 hover:bg-yellow-500 text-white'"
        >
          <svg v-if="!state.paused" class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" />
          </svg>
          <svg v-else class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd" />
          </svg>
          {{ state.paused ? 'Resume' : 'Pause' }}
        </button>

        <!-- Stop Button -->
        <button
          @click="emit('stop')"
          :disabled="!state.running"
          class="min-h-[44px] px-5 py-2.5 rounded-lg font-medium transition-colors flex items-center gap-2"
          :class="!state.running
            ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
            : 'bg-red-600 hover:bg-red-500 text-white'"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clip-rule="evenodd" />
          </svg>
          Stop
        </button>
      </div>

      <div class="flex items-center gap-6 text-sm text-gray-300">
        <div>
          <span class="text-gray-500">Loop:</span>
          <span class="ml-1 font-mono">{{ state.loop_count }}</span>
        </div>
        <div v-if="queueEnabled" class="text-blue-400">
          Queue: {{ queueMode }} ({{ smartMainMode }})
        </div>
        <div v-else>
          <span class="text-gray-500">Profile:</span>
          <span class="ml-1">{{ currentProfile }}</span>
        </div>
      </div>
    </div>
  </footer>
</template>
