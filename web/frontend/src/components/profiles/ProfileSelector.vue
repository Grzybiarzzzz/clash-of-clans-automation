<script setup>
import { ref, computed } from 'vue'
import { useBotState } from '../../composables/useBotState'

const emit = defineEmits(['profile-change'])

const { state } = useBotState()

// Available profiles matching the backend
const profiles = [
  { id: 'Farming', name: 'Farming', icon: '🌾', description: 'Resource-focused attacks' },
  { id: 'Trophy Push', name: 'Trophy Push', icon: '🏆', description: 'Target lower TH bases', deprecated: true },
  { id: 'Derank', name: 'Derank', icon: '📉', description: 'Throw attacks until target trophies', deprecated: true },
  { id: 'SGoblin Farm', name: 'SGoblin Farm', icon: '👺', description: 'Super Goblin split-army farming' },
  { id: 'SBarb Farm', name: 'SBarb Farm', icon: '⚔️', description: 'Super Barbarian farming with spells' },
  { id: 'BB Elixir', name: 'BB Elixir', icon: '⚡', description: 'Builder Base elixir farming' },
  { id: 'BB Gold', name: 'BB Gold', icon: '🪙', description: 'Builder Base gold farming' },
  { id: 'Achievement Farm', name: 'Achievement Farm', icon: '🎯', description: 'Specialized building destruction' },
  { id: 'Custom', name: 'Custom', icon: '⚙️', description: 'User-defined settings' }
]

// Technical details for each profile
const profileDetails = {
  'Farming': {
    title: 'Farming Mode',
    sections: [
      {
        heading: 'Army Composition',
        items: [
          'Configure troop counts in Settings → Army section',
          'Troops are deployed using hotkeys 1-7 in sequence',
          'Each slot deploys the configured number of troops',
          'Heroes deploy after troops with configured ability timing'
        ]
      },
      {
        heading: 'Attack Logic',
        items: [
          'Detects air defenses and calculates lightning spells needed',
          'Chooses attack side based on setting (random/TH side/opposite TH)',
          'Skips bases below minimum resource threshold',
          'Skips bases above max TH level setting'
        ]
      },
      {
        heading: 'Recommended Settings',
        items: [
          'Set minimum resources to filter low-value bases',
          'Configure hero ability timing (seconds after deployment)',
          'Enable reinforcements if clan castle troops available'
        ]
      }
    ]
  },
  'Trophy Push': {
    title: 'Trophy Push Mode (Deprecated)',
    sections: [
      {
        heading: '⚠️ Deprecation Notice',
        items: [
          'Trophies have been removed from main base in recent updates',
          'This mode is kept for legacy compatibility only',
          'Consider using Farming or SBarb Farm instead'
        ]
      },
      {
        heading: 'Original Behavior',
        items: [
          'Targeted lower TH bases for easier wins',
          'Focused on trophy gain over resource collection',
          'Used full army deployment for maximum destruction'
        ]
      }
    ]
  },
  'Derank': {
    title: 'Derank Mode (Deprecated)',
    sections: [
      {
        heading: '⚠️ Deprecation Notice',
        items: [
          'Trophies have been removed from main base in recent updates',
          'This mode is kept for legacy compatibility only',
          'No longer functional for its original purpose'
        ]
      },
      {
        heading: 'Original Behavior',
        items: [
          'Threw attacks to lose trophies intentionally',
          'Continued until target trophy count reached',
          'Used minimal troop deployment to lose quickly'
        ]
      }
    ]
  },
  'SGoblin Farm': {
    title: 'Super Goblin Farm Mode',
    sections: [
      {
        heading: 'Army Requirements',
        items: [
          'Entire army must be Super Goblins',
          'Bot looks for first non-zero slot for the hotkey',
          'This allows involuntary event troops in other slots',
          'Heroes and Siege Machine also deployed'
        ]
      },
      {
        heading: 'Attack Strategy',
        items: [
          'Splits army on opposite sides (up/down)',
          '4-pass deployment: 2 passes per side',
          'Optional wall breakers deploy before goblins',
          'All 4 heroes deploy at first side position',
          'Siege machine (Z key) deploys after heroes'
        ]
      },
      {
        heading: 'Spell Casting (Optional)',
        items: [
          'Enable "Cast Spells on Achievement Buildings"',
          'Scans for priority buildings during attack window',
          'Deploys 1 Earthquake + 10 Lightning on target',
          'Uses building center coordinates with ±3px spread'
        ]
      },
      {
        heading: 'Recommended Settings',
        items: [
          'Enable spell casting for extra achievement progress',
          'Configure achievement building priority order',
          'Consider enabling wall breakers for better penetration'
        ]
      }
    ]
  },
  'SBarb Farm': {
    title: 'Super Barbarian Farm Mode',
    sections: [
      {
        heading: 'Army Requirements',
        items: [
          'Entire army must be Super Barbarians',
          'Bot looks for first non-zero slot for the hotkey',
          'This allows involuntary event troops in other slots',
          '2 Earthquake + 9 Lightning spells (or 1 EQ + 10 Lightning with achievement targeting)'
        ]
      },
      {
        heading: 'Deployment Modes',
        items: [
          'Standard Mode: Configurable hero timing and order',
          'Turbo-Fast Mode: ~16 clicks/sec using Windows API',
          'Turbo mode overrides hero timing settings',
          'Turbo mode highly recommended for speed'
        ]
      },
      {
        heading: 'Achievement Building Targeting',
        items: [
          'Enable "Cast Spells on Achievement Buildings"',
          'Three targeting modes available:',
          '• Target: Scan only priority building, skip if not found',
          '• Clumps (Recommended): Scan all, prioritize clusters of 2+',
          '• First Detected: Attack first match immediately'
        ]
      },
      {
        heading: 'Attack Flow',
        items: [
          'Background scan starts during troop deployment',
          'Spells cast on detected buildings mid-attack',
          '10-second timer before surrender (or 50% destruction)',
          'Attack duration and buildings destroyed logged to CSV'
        ]
      },
      {
        heading: 'Recommended Settings',
        items: [
          'Enable Turbo-Fast Deployment for maximum speed',
          'Enable spell casting on achievement buildings',
          'Use Clumps targeting mode for best results',
          'Configure priority list with most wanted buildings first'
        ]
      }
    ]
  },
  'BB Elixir': {
    title: 'Builder Base Elixir Mode',
    sections: [
      {
        heading: 'Strategy',
        items: [
          'Quick surrender farming for elixir',
          'Deploys single unit to enable surrender',
          'Immediately surrenders after deployment',
          'Minimal battle time for fast cycling'
        ]
      },
      {
        heading: 'Army Requirements',
        items: [
          'Any Builder Base army works',
          'Only one unit is deployed per attack',
          'Focus is on speed, not winning'
        ]
      },
      {
        heading: 'Use Case',
        items: [
          'Quickly deplete BB attack attempts',
          'Farm elixir when you don\'t care about winning',
          'Useful for rushing Builder Base upgrades'
        ]
      }
    ]
  },
  'BB Gold': {
    title: 'Builder Base Gold Mode',
    sections: [
      {
        heading: 'Strategy',
        items: [
          'Full attack for maximum gold and stars',
          'Uses state machine for battle lifecycle',
          'Deploys Battle Machine + 6 Night Witches',
          'Activates abilities during battle'
        ]
      },
      {
        heading: 'Army Requirements',
        items: [
          'Battle Machine (hero) required',
          'Night Witches in first army slot',
          'At least 6 Night Witches recommended'
        ]
      },
      {
        heading: 'State Machine',
        items: [
          'IN_BASE → SEARCHING → ATTACK_READY',
          'ATTACK_READY → BATTLE_ACTIVE → BATTLE_ENDING',
          'BATTLE_ENDING → END_SCREEN → RETURNING_HOME',
          'Handles errors and ghost attacks automatically'
        ]
      },
      {
        heading: 'Loot Collection',
        items: [
          'Collects loot every N attacks (configurable)',
          'Default: collect every 12 attacks',
          'Attack duration and stars logged to CSV'
        ]
      }
    ]
  },
  'Achievement Farm': {
    title: 'Achievement Farm Mode',
    sections: [
      {
        heading: 'Purpose',
        items: [
          'Specialized for destroying achievement buildings',
          'Targets: Eagle Artillery, Monolith, X-Bow, Inferno Tower',
          'Also: Scattershot, Spell Tower, Multi-Archer Tower',
          'And: Ricochet Cannon, Firespitter, Multi-Gear Tower'
        ]
      },
      {
        heading: 'Army Requirements',
        items: [
          'Spell army only: Earthquake + Lightning spells',
          'Recommended: 2 Earthquake + 9 Lightning',
          'No troops needed - pure spell attacks'
        ]
      },
      {
        heading: 'Targeting Modes',
        items: [
          'Target Mode: Scan only selected type, skip if not found',
          'Clumps Mode: Scan all types, prioritize clusters (2+ within 125px)',
          'First Detected: Scan sequentially, attack first match'
        ]
      },
      {
        heading: 'Attack Logic',
        items: [
          'Scans base for enabled building types',
          'Calculates building center from template match',
          'Deploys 1 Earthquake + 10 Lightning on target',
          'Lightning spells use ±3px random spread'
        ]
      },
      {
        heading: 'Recommended Settings',
        items: [
          'Use Clumps mode for efficiency (hit multiple buildings)',
          'Configure priority list based on achievement needs',
          'Disable buildings you don\'t need to target',
          'Enable parallel scanning for faster detection'
        ]
      }
    ]
  },
  'Custom': {
    title: 'Custom Mode',
    sections: [
      {
        heading: 'Overview',
        items: [
          'Fully user-configurable attack profile',
          'All settings can be customized independently',
          'Good for testing or specialized strategies'
        ]
      },
      {
        heading: 'Configuration',
        items: [
          'Set your own troop counts per slot',
          'Configure hero ability timings',
          'Set resource and TH level thresholds',
          'Choose attack side preference'
        ]
      },
      {
        heading: 'Use Cases',
        items: [
          'Experimenting with new strategies',
          'Mixed army compositions',
          'Custom automation requirements'
        ]
      }
    ]
  }
}

const isDropdownOpen = ref(false)
const showDetailsModal = ref(false)
const selectedDetailsProfile = ref(null)

const currentProfile = computed(() => {
  return profiles.find(p => p.id === state.current_profile) || profiles[0]
})

function selectProfile(profile) {
  isDropdownOpen.value = false
  emit('profile-change', profile.id)
}

function toggleDropdown() {
  isDropdownOpen.value = !isDropdownOpen.value
}

function openDetails(profile, event) {
  event.stopPropagation()
  selectedDetailsProfile.value = profile
  showDetailsModal.value = true
}

function closeDetails() {
  showDetailsModal.value = false
  selectedDetailsProfile.value = null
}
</script>

<template>
  <div class="p-4 md:p-6 space-y-4 md:space-y-6">
    <div>
      <h2 class="text-xl md:text-2xl font-bold text-white">Profiles</h2>
      <p class="text-sm md:text-base text-gray-400 mt-1">Select an attack profile to configure the bot's behavior.</p>
    </div>

    <!-- Current Profile Card -->
    <div class="bg-gray-800 rounded-xl border border-gray-700 p-4 md:p-6">
      <h3 class="text-xs md:text-sm font-medium text-gray-400 uppercase tracking-wider mb-3 md:mb-4">Current Profile</h3>

      <!-- Dropdown Trigger -->
      <div class="relative">
        <button
          @click="toggleDropdown"
          class="w-full flex items-center justify-between bg-gray-700 hover:bg-gray-600 active:bg-gray-600 rounded-lg p-3 md:p-4 transition-colors min-h-[60px]"
        >
          <div class="flex items-center gap-3 md:gap-4">
            <span class="text-2xl md:text-3xl">{{ currentProfile.icon }}</span>
            <div class="text-left">
              <div class="text-base md:text-lg font-semibold text-white">{{ currentProfile.name }}</div>
              <div class="text-xs md:text-sm text-gray-400">{{ currentProfile.description }}</div>
            </div>
          </div>
          <svg
            class="w-5 h-5 text-gray-400 transition-transform flex-shrink-0 ml-2"
            :class="{ 'rotate-180': isDropdownOpen }"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        <!-- Dropdown Menu -->
        <div
          v-show="isDropdownOpen"
          class="absolute z-10 w-full mt-2 bg-gray-700 rounded-lg shadow-xl border border-gray-600 overflow-hidden max-h-[60vh] overflow-y-auto"
        >
          <button
            v-for="profile in profiles"
            :key="profile.id"
            @click="selectProfile(profile)"
            class="w-full flex items-center gap-3 md:gap-4 p-3 md:p-4 hover:bg-gray-600 active:bg-gray-600 transition-colors text-left min-h-[56px]"
            :class="{
              'bg-blue-600 hover:bg-blue-500': profile.id === state.current_profile
            }"
          >
            <span class="text-xl md:text-2xl">{{ profile.icon }}</span>
            <div>
              <div class="text-sm md:text-base font-medium text-white">{{ profile.name }}</div>
              <div class="text-xs md:text-sm text-gray-300">{{ profile.description }}</div>
            </div>
          </button>
        </div>
      </div>
    </div>

    <!-- Profile Cards Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 md:gap-4">
      <div
        v-for="profile in profiles"
        :key="profile.id"
        class="bg-gray-800 rounded-xl border p-3 md:p-4 transition-all min-h-[70px]"
        :class="{
          'border-blue-500 ring-2 ring-blue-500/20': profile.id === state.current_profile,
          'border-gray-700 hover:border-gray-600': profile.id !== state.current_profile,
          'opacity-60': profile.deprecated
        }"
      >
        <div class="flex items-start gap-3">
          <span class="text-xl md:text-2xl">{{ profile.icon }}</span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <div class="text-sm md:text-base font-medium text-white">{{ profile.name }}</div>
              <span v-if="profile.deprecated" class="px-1.5 py-0.5 bg-yellow-600/30 text-yellow-500 text-xs rounded">Deprecated</span>
            </div>
            <div class="text-xs md:text-sm text-gray-400 mt-1">{{ profile.description }}</div>

            <!-- Action Buttons -->
            <div class="flex gap-2 mt-3">
              <button
                @click="selectProfile(profile)"
                class="px-3 py-1.5 text-xs font-medium rounded-lg transition-colors"
                :class="profile.id === state.current_profile
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 hover:bg-gray-600 text-gray-300'"
              >
                {{ profile.id === state.current_profile ? 'Selected' : 'Select' }}
              </button>
              <button
                @click="openDetails(profile, $event)"
                class="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs font-medium rounded-lg transition-colors flex items-center gap-1"
              >
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Details
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Details Modal -->
    <div
      v-if="showDetailsModal && selectedDetailsProfile"
      class="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      <!-- Backdrop -->
      <div
        class="absolute inset-0 bg-black/70"
        @click="closeDetails"
      ></div>

      <!-- Modal Content -->
      <div class="relative bg-gray-800 rounded-xl border border-gray-700 w-full max-w-2xl max-h-[85vh] overflow-hidden shadow-2xl">
        <!-- Header -->
        <div class="flex items-center justify-between p-4 border-b border-gray-700 bg-gray-800 sticky top-0">
          <div class="flex items-center gap-3">
            <span class="text-2xl">{{ selectedDetailsProfile.icon }}</span>
            <div>
              <h3 class="text-lg font-bold text-white">{{ profileDetails[selectedDetailsProfile.id]?.title || selectedDetailsProfile.name }}</h3>
              <p class="text-sm text-gray-400">Technical Information</p>
            </div>
          </div>
          <button
            @click="closeDetails"
            class="p-2 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Body -->
        <div class="p-4 overflow-y-auto max-h-[calc(85vh-80px)] space-y-4">
          <template v-if="profileDetails[selectedDetailsProfile.id]">
            <div
              v-for="(section, sectionIndex) in profileDetails[selectedDetailsProfile.id].sections"
              :key="sectionIndex"
              class="bg-gray-700/50 rounded-lg p-4"
            >
              <h4 class="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <span class="w-1.5 h-1.5 bg-blue-500 rounded-full"></span>
                {{ section.heading }}
              </h4>
              <ul class="space-y-2">
                <li
                  v-for="(item, itemIndex) in section.items"
                  :key="itemIndex"
                  class="text-sm text-gray-300 flex items-start gap-2"
                >
                  <span class="text-gray-500 mt-1">•</span>
                  <span>{{ item }}</span>
                </li>
              </ul>
            </div>
          </template>
          <div v-else class="text-gray-400 text-center py-8">
            No detailed information available for this profile.
          </div>
        </div>

        <!-- Footer -->
        <div class="p-4 border-t border-gray-700 bg-gray-800 sticky bottom-0 flex justify-between items-center">
          <button
            @click="selectProfile(selectedDetailsProfile); closeDetails()"
            class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-colors"
          >
            Select This Profile
          </button>
          <button
            @click="closeDetails"
            class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
