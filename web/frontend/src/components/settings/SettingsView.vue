<script setup>
import { computed, ref } from 'vue'
import { useBotState } from '../../composables/useBotState'
import CollapsibleSection from './CollapsibleSection.vue'

const { state } = useBotState()

const emit = defineEmits(['setting-change'])

// Computed properties for profile-specific visibility
const profile = computed(() => state.current_profile)

const showTroops = computed(() => {
  return !['Derank', 'BB Elixir', 'BB Gold', 'Achievement Farm'].includes(profile.value)
})

const showLightningDamage = computed(() => {
  return !['Derank', 'SGoblin Farm', 'BB Elixir', 'BB Gold'].includes(profile.value)
})

const showMinResources = computed(() => {
  return !['Derank', 'BB Elixir', 'BB Gold', 'Achievement Farm'].includes(profile.value)
})

const showMaxTH = computed(() => {
  return ['Farming', 'Trophy Push', 'Custom'].includes(profile.value)
})

const showHeroTimings = computed(() => {
  return !['Derank', 'BB Elixir', 'BB Gold', 'Achievement Farm'].includes(profile.value)
})

const showSGoblinOptions = computed(() => profile.value === 'SGoblin Farm')
const showSBarbOptions = computed(() => profile.value === 'SBarb Farm')
const showBBGoldOptions = computed(() => profile.value === 'BB Gold')
const showAchievementOptions = computed(() => ['Achievement Farm', 'SBarb Farm', 'SGoblin Farm'].includes(profile.value))

// Settings from state
const troopCounts = computed(() => state.settings?.troop_counts || [0, 0, 0, 0, 0, 0, 0])
const minResources = computed(() => state.settings?.min_resources ?? 100000)
const maxTHLevel = computed(() => state.settings?.max_th_level ?? 17)
const lightningDamage = computed(() => state.settings?.lightning_damage ?? 600)
const queenTiming = computed(() => state.settings?.queen_ability_timing ?? 15)
const kingTiming = computed(() => state.settings?.king_ability_timing ?? 15)
const wardenTiming = computed(() => state.settings?.warden_ability_timing ?? 15)
const rcTiming = computed(() => state.settings?.rc_ability_timing ?? 15)

// SGoblin options
const sgoblinCastSpells = computed(() => state.settings?.sgoblin_cast_spells ?? false)
const sgoblinUseWallbreakers = computed(() => state.settings?.sgoblin_use_wallbreakers ?? false)

// SBarb options
const sbarbTurboDeployment = computed(() => state.settings?.sbarb_turbo_deployment ?? false)
const sbarbHeroesFirst = computed(() => state.settings?.sbarb_heroes_first ?? false)
const sbarbQueenArrow = computed(() => state.settings?.sbarb_queen_arrow_spells ?? false)
const sbarbCastSpells = computed(() => state.settings?.sbarb_cast_spells ?? false)
const sbarbTargetMode = computed(() => state.settings?.sbarb_cast_spells_target_mode ?? 'clumps')

// BB Gold options
const bbGoldTroopMode = computed(() => state.settings?.bb_gold_troop_mode ?? 'night_witches')
const bbGoldTryFor3Stars = computed(() => state.settings?.bb_gold_try_3_stars ?? false)
const bbGoldDragonDebugPositions = computed(() => state.settings?.bb_gold_dragon_debug_positions ?? false)

// BB Gold troop mode options for dropdown
const bbGoldTroopModeOptions = [
  { value: 'night_witches', label: 'Night Witches', description: 'Battle Machine + 6 Night Witches' },
  { value: 'bomber_night_witches', label: 'Bomber + Night Witches', description: 'Bomber in slot 1 with 22s ability recast' },
  { value: 'baby_dragons', label: 'Baby Dragons', description: '6 Baby Dragons spread around boundary' }
]

// Queue settings
const queueEnabled = computed(() => state.settings?.queue_enabled ?? false)
const queueMode = computed(() => state.settings?.queue_mode ?? 'smart')
const smartModeConfig = computed(() => state.settings?.smart_mode_config ?? {})
const smartMainMode = computed(() => smartModeConfig.value.main_base_mode ?? 'SBarb Farm')
const smartGoldThreshold = computed(() => smartModeConfig.value.storage_targets?.gold_threshold ?? 100)
const smartElixirThreshold = computed(() => smartModeConfig.value.storage_targets?.elixir_threshold ?? 100)
const smartWaitForDE = computed(() => smartModeConfig.value.storage_targets?.wait_for_de ?? false)
const smartDEThreshold = computed(() => smartModeConfig.value.storage_targets?.de_threshold ?? 100)
const smartAfterBB = computed(() => smartModeConfig.value.after_bb_behavior ?? 'stop')
const smartBBGoldMode = computed(() => smartModeConfig.value.bb_gold_mode ?? 'night_witches')
const achievementDuration = computed(() => state.settings?.achievement_farm_end_config?.duration_minutes ?? 20)

// Global settings
const reinforcementsEnabled = computed(() => state.settings?.reinforcements_enabled ?? false)
const parallelScanning = computed(() => state.settings?.parallel_scanning ?? false)
const gpuScanning = computed(() => state.settings?.gpu_scanning ?? false)
const skipOnTHFail = computed(() => state.settings?.skip_on_th_fail ?? true)
const overlayEnabled = computed(() => state.settings?.overlay_enabled ?? false)
const overlayHideLowConf = computed(() => state.settings?.overlay_hide_low_conf ?? false)
const autoPauseEnabled = computed(() => state.settings?.auto_pause_enabled ?? false)
const breakInterval = computed(() => state.settings?.break_interval ?? 60)
const breakDuration = computed(() => state.settings?.break_duration ?? 5)
const bbCollectInterval = computed(() => state.settings?.bb_collect_interval ?? 12)

// Achievement building priority
const defaultPriorityList = [
  'eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot',
  'spell_tower', 'multi_archer_tower', 'ricochet_cannon', 'firespitter', 'multi_gear_tower'
]
const achievementPriorityList = computed(() => state.settings?.achievement_priority_list ?? defaultPriorityList)

// Building scan toggles
const buildingScanSettings = computed(() => ({
  eagle_artillery: state.settings?.achievement_scan_eagle_artillery ?? true,
  monolith: state.settings?.achievement_scan_monolith ?? true,
  xbow: state.settings?.achievement_scan_xbow ?? true,
  inferno_tower: state.settings?.achievement_scan_inferno_tower ?? true,
  scattershot: state.settings?.achievement_scan_scattershot ?? true,
  spell_tower: state.settings?.achievement_scan_spell_tower ?? true,
  multi_archer_tower: state.settings?.achievement_scan_multi_archer_tower ?? true,
  ricochet_cannon: state.settings?.achievement_scan_ricochet_cannon ?? true,
  firespitter: state.settings?.achievement_scan_firespitter ?? true,
  multi_gear_tower: state.settings?.achievement_scan_multi_gear_tower ?? true,
}))

// Building display names
const buildingDisplayNames = {
  eagle_artillery: 'Eagle Artillery',
  monolith: 'Monolith',
  xbow: 'X-Bow',
  inferno_tower: 'Inferno Tower',
  scattershot: 'Scattershot',
  spell_tower: 'Spell Tower',
  multi_archer_tower: 'Multi-Archer Tower',
  ricochet_cannon: 'Ricochet Cannon',
  firespitter: 'Firespitter',
  multi_gear_tower: 'Multi-Gear Tower',
}

// Main base modes for queue
const mainBaseModes = ['Farming', 'SBarb Farm', 'SGoblin Farm', 'Achievement Farm', 'Custom']

// Drag state for priority list
const draggedIndex = ref(null)

// Handlers
function updateSetting(key, value) {
  emit('setting-change', { key, value })
}

function updateTroopCount(index, value) {
  const newCounts = [...troopCounts.value]
  newCounts[index] = parseInt(value) || 0
  updateSetting('troop_counts', newCounts)
}

function updateSmartModeConfig(key, value) {
  const config = { ...smartModeConfig.value }
  if (key.startsWith('storage_targets.')) {
    const subKey = key.replace('storage_targets.', '')
    config.storage_targets = { ...config.storage_targets, [subKey]: value }
  } else {
    config[key] = value
  }
  updateSetting('smart_mode_config', config)
}

function updateAchievementConfig(key, value) {
  const config = { ...(state.settings?.achievement_farm_end_config ?? {}) }
  config[key] = value
  updateSetting('achievement_farm_end_config', config)
}

function toggleBuildingScan(building) {
  updateSetting(`achievement_scan_${building}`, !buildingScanSettings.value[building])
}

// Priority list drag handlers
function onDragStart(index) {
  draggedIndex.value = index
}

function onDragOver(event, index) {
  event.preventDefault()
  if (draggedIndex.value === null || draggedIndex.value === index) return
}

function onDrop(index) {
  if (draggedIndex.value === null || draggedIndex.value === index) {
    draggedIndex.value = null
    return
  }

  const newList = [...achievementPriorityList.value]
  const [removed] = newList.splice(draggedIndex.value, 1)
  newList.splice(index, 0, removed)
  updateSetting('achievement_priority_list', newList)
  draggedIndex.value = null
}

function onDragEnd() {
  draggedIndex.value = null
}

function movePriorityUp(index) {
  if (index === 0) return
  const newList = [...achievementPriorityList.value]
  ;[newList[index], newList[index - 1]] = [newList[index - 1], newList[index]]
  updateSetting('achievement_priority_list', newList)
}

function movePriorityDown(index) {
  if (index === achievementPriorityList.value.length - 1) return
  const newList = [...achievementPriorityList.value]
  ;[newList[index], newList[index + 1]] = [newList[index + 1], newList[index]]
  updateSetting('achievement_priority_list', newList)
}

function resetPriorityList() {
  updateSetting('achievement_priority_list', [...defaultPriorityList])
}
</script>

<template>
  <div class="p-4 md:p-6 space-y-4 md:space-y-6">
    <div>
      <h2 class="text-xl md:text-2xl font-bold text-white">Settings</h2>
      <p class="text-sm md:text-base text-gray-400 mt-1">Configure bot behavior for {{ profile }}.</p>
    </div>

    <!-- Army Section -->
    <CollapsibleSection v-if="showTroops || showLightningDamage" title="Army" icon="🪖" :defaultOpen="false">
      <div class="space-y-4">
        <!-- Troop Counts -->
        <div v-if="showTroops" class="space-y-3">
          <div class="text-sm text-gray-400 mb-2">Troop counts per deployment slot</div>
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div v-for="(count, index) in troopCounts" :key="index" class="bg-gray-700/50 rounded-lg p-3">
              <label class="text-xs text-gray-500 block mb-1">Slot {{ index + 1 }}</label>
              <input
                type="number"
                :value="count"
                @input="updateTroopCount(index, $event.target.value)"
                min="0"
                max="99"
                class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>
        </div>

        <!-- Lightning Damage -->
        <div v-if="showLightningDamage" class="bg-gray-700/50 rounded-lg p-4">
          <label class="text-sm text-gray-400 block mb-2">Lightning Spell Damage</label>
          <input
            type="number"
            :value="lightningDamage"
            @input="updateSetting('lightning_damage', parseInt($event.target.value) || 600)"
            min="100"
            max="800"
            step="25"
            class="w-full sm:w-32 bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
          />
          <p class="text-xs text-gray-500 mt-1">Used to calculate spells needed per air defense</p>
        </div>
      </div>
    </CollapsibleSection>

    <!-- Attack Settings -->
    <CollapsibleSection v-if="showMinResources || showMaxTH || showHeroTimings" title="Attack Settings" icon="⚔️" :defaultOpen="false">
      <div class="space-y-4">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <!-- Min Resources -->
          <div v-if="showMinResources" class="bg-gray-700/50 rounded-lg p-4">
            <label class="text-sm text-gray-400 block mb-2">Minimum Resources</label>
            <input
              type="number"
              :value="minResources"
              @input="updateSetting('min_resources', parseInt($event.target.value) || 100000)"
              min="0"
              max="2000000"
              step="10000"
              class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
            />
            <p class="text-xs text-gray-500 mt-1">Skip bases below this gold+elixir total</p>
          </div>

          <!-- Max TH Level -->
          <div v-if="showMaxTH" class="bg-gray-700/50 rounded-lg p-4">
            <label class="text-sm text-gray-400 block mb-2">Max Town Hall Level</label>
            <input
              type="number"
              :value="maxTHLevel"
              @input="updateSetting('max_th_level', parseInt($event.target.value) || 17)"
              min="1"
              max="17"
              class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
            />
            <p class="text-xs text-gray-500 mt-1">Skip bases with higher TH level</p>
          </div>
        </div>

        <!-- Hero Ability Timing -->
        <div v-if="showHeroTimings">
          <div class="text-sm text-gray-400 mb-3">Hero Ability Timing (seconds after deployment, -1 = disabled)</div>
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div class="bg-gray-700/50 rounded-lg p-3">
              <label class="text-xs text-gray-500 block mb-1">King</label>
              <input
                type="number"
                :value="kingTiming"
                @input="updateSetting('king_ability_timing', parseInt($event.target.value))"
                min="-1"
                max="60"
                class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div class="bg-gray-700/50 rounded-lg p-3">
              <label class="text-xs text-gray-500 block mb-1">Queen</label>
              <input
                type="number"
                :value="queenTiming"
                @input="updateSetting('queen_ability_timing', parseInt($event.target.value))"
                min="-1"
                max="60"
                class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div class="bg-gray-700/50 rounded-lg p-3">
              <label class="text-xs text-gray-500 block mb-1">Warden</label>
              <input
                type="number"
                :value="wardenTiming"
                @input="updateSetting('warden_ability_timing', parseInt($event.target.value))"
                min="-1"
                max="60"
                class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div class="bg-gray-700/50 rounded-lg p-3">
              <label class="text-xs text-gray-500 block mb-1">Champion</label>
              <input
                type="number"
                :value="rcTiming"
                @input="updateSetting('rc_ability_timing', parseInt($event.target.value))"
                min="-1"
                max="60"
                class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>
        </div>
      </div>
    </CollapsibleSection>

    <!-- SGoblin Farm Options -->
    <CollapsibleSection v-if="showSGoblinOptions" title="SGoblin Farm Options" icon="👺" :defaultOpen="false">
      <div class="space-y-3">
        <label class="flex items-center gap-3 cursor-pointer p-3 bg-gray-700/50 rounded-lg hover:bg-gray-700 transition-colors">
          <input
            type="checkbox"
            :checked="sgoblinCastSpells"
            @change="updateSetting('sgoblin_cast_spells', $event.target.checked)"
            class="w-5 h-5 rounded border-gray-600 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
          />
          <div>
            <span class="text-white">Cast Spells on Achievement Buildings</span>
            <p class="text-xs text-gray-500">Scan and cast spells during attack window</p>
          </div>
        </label>

        <label class="flex items-center gap-3 cursor-pointer p-3 bg-gray-700/50 rounded-lg hover:bg-gray-700 transition-colors">
          <input
            type="checkbox"
            :checked="sgoblinUseWallbreakers"
            @change="updateSetting('sgoblin_use_wallbreakers', $event.target.checked)"
            class="w-5 h-5 rounded border-gray-600 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
          />
          <div>
            <span class="text-white">Use Wall Breakers</span>
            <p class="text-xs text-gray-500">Deploy wall breakers before goblins</p>
          </div>
        </label>
      </div>
    </CollapsibleSection>

    <!-- SBarb Farm Options -->
    <CollapsibleSection v-if="showSBarbOptions" title="SBarb Farm Options" icon="⚔️" :defaultOpen="false">
      <div class="space-y-3">
        <!-- Turbo Deployment - shown first, hides other options when enabled -->
        <label class="flex items-center gap-3 cursor-pointer p-3 bg-blue-900/30 border border-blue-700/50 rounded-lg hover:bg-blue-900/40 transition-colors">
          <input
            type="checkbox"
            :checked="sbarbTurboDeployment"
            @change="updateSetting('sbarb_turbo_deployment', $event.target.checked)"
            class="w-5 h-5 rounded border-gray-600 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
          />
          <div>
            <span class="text-white font-medium">Turbo-Fast Deployment</span>
            <p class="text-xs text-gray-400">~16 CPS using Windows API, overrides hero timing/order settings</p>
          </div>
        </label>

        <!-- Standard mode options - hidden when turbo is enabled -->
        <template v-if="!sbarbTurboDeployment">
          <label class="flex items-center gap-3 cursor-pointer p-3 bg-gray-700/50 rounded-lg hover:bg-gray-700 transition-colors">
            <input
              type="checkbox"
              :checked="sbarbHeroesFirst"
              @change="updateSetting('sbarb_heroes_first', $event.target.checked)"
              class="w-5 h-5 rounded border-gray-600 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
            />
            <div>
              <span class="text-white">Deploy Heroes First</span>
              <p class="text-xs text-gray-500">Heroes deploy before barbarians</p>
            </div>
          </label>

          <label class="flex items-center gap-3 cursor-pointer p-3 bg-gray-700/50 rounded-lg hover:bg-gray-700 transition-colors">
            <input
              type="checkbox"
              :checked="sbarbQueenArrow"
              @change="updateSetting('sbarb_queen_arrow_spells', $event.target.checked)"
              class="w-5 h-5 rounded border-gray-600 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
            />
            <div>
              <span class="text-white">Queen Arrow Targeting (WIP)</span>
              <p class="text-xs text-gray-500">Cast spells where queen arrow points</p>
            </div>
          </label>
        </template>

        <!-- Cast spells - shown in both modes -->
        <label class="flex items-center gap-3 cursor-pointer p-3 bg-gray-700/50 rounded-lg hover:bg-gray-700 transition-colors">
          <input
            type="checkbox"
            :checked="sbarbCastSpells"
            @change="updateSetting('sbarb_cast_spells', $event.target.checked)"
            class="w-5 h-5 rounded border-gray-600 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
          />
          <div>
            <span class="text-white">Cast Spells on Achievement Buildings</span>
            <p class="text-xs text-gray-500">Scan and cast spells during attack window</p>
          </div>
        </label>

        <!-- Targeting Mode - shown when Cast Spells is enabled -->
        <div v-if="sbarbCastSpells" class="bg-gray-700/50 rounded-lg p-4">
          <label class="text-sm text-gray-400 block mb-2">Targeting Mode</label>
          <div class="flex gap-2 flex-wrap">
            <button
              @click="updateSetting('sbarb_cast_spells_target_mode', 'target')"
              class="px-3 py-2 rounded-lg text-sm font-medium transition-colors"
              :class="sbarbTargetMode === 'target' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-600'"
            >
              Target
            </button>
            <button
              @click="updateSetting('sbarb_cast_spells_target_mode', 'clumps')"
              class="px-3 py-2 rounded-lg text-sm font-medium transition-colors"
              :class="sbarbTargetMode === 'clumps' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-600'"
            >
              Clumps
            </button>
            <button
              @click="updateSetting('sbarb_cast_spells_target_mode', 'first_detected')"
              class="px-3 py-2 rounded-lg text-sm font-medium transition-colors"
              :class="sbarbTargetMode === 'first_detected' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-600'"
            >
              First Detected
            </button>
          </div>
          <p class="text-xs text-gray-500 mt-2">
            <span v-if="sbarbTargetMode === 'target'">Scan only for priority building, skip if not found</span>
            <span v-else-if="sbarbTargetMode === 'clumps'">Scan all buildings, prioritize clusters of 2+</span>
            <span v-else>Scan sequentially, attack first match immediately</span>
          </p>
        </div>
      </div>
    </CollapsibleSection>

    <!-- BB Gold Options -->
    <CollapsibleSection v-if="showBBGoldOptions" title="BB Gold Options" icon="⚙️" :defaultOpen="false">
      <div class="space-y-3">
        <div class="p-3 bg-gray-700/50 rounded-lg">
          <label class="block text-white font-medium mb-2">Troop Mode</label>
          <select
            :value="bbGoldTroopMode"
            @change="updateSetting('bb_gold_troop_mode', $event.target.value)"
            class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
          >
            <option v-for="option in bbGoldTroopModeOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
          <p class="text-xs text-gray-500 mt-2">
            {{ bbGoldTroopModeOptions.find(o => o.value === bbGoldTroopMode)?.description || 'Select a troop composition' }}
          </p>
        </div>

        <!-- Baby Dragons: Try for 3 stars option -->
        <div v-if="bbGoldTroopMode === 'baby_dragons'" class="p-3 bg-gray-700/50 rounded-lg">
          <label class="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              :checked="bbGoldTryFor3Stars"
              @change="updateSetting('bb_gold_try_3_stars', $event.target.checked)"
              class="w-5 h-5 rounded border-gray-600 text-blue-600 focus:ring-blue-500"
            />
            <div>
              <span class="text-white">Try for 3 Stars</span>
              <p class="text-xs text-gray-500">Don't surrender at 2 stars, keep attacking for 3rd star</p>
            </div>
          </label>
        </div>

        <!-- Baby Dragons: Debug detection -->
        <div v-if="bbGoldTroopMode === 'baby_dragons'" class="p-3 bg-gray-700/50 rounded-lg">
          <label class="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              :checked="bbGoldDragonDebugPositions"
              @change="updateSetting('bb_gold_dragon_debug_positions', $event.target.checked)"
              class="w-5 h-5 rounded border-gray-600 text-blue-600 focus:ring-blue-500"
            />
            <div>
              <span class="text-white">Debug Detection (mask + positions)</span>
              <p class="text-xs text-gray-500">Save debug image showing red mask, overlay, and deployment positions</p>
            </div>
          </label>
        </div>
      </div>
    </CollapsibleSection>

    <!-- Queue System Settings -->
    <CollapsibleSection title="Queue System" icon="📋" :defaultOpen="false">
      <div class="space-y-4">
        <!-- Queue Enable/Mode -->
        <div class="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg">
          <div>
            <span class="text-white font-medium">Queue System</span>
            <p class="text-xs text-gray-500">Auto-switch between modes based on conditions</p>
          </div>
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              :checked="queueEnabled"
              @change="updateSetting('queue_enabled', $event.target.checked)"
              class="w-5 h-5 rounded border-gray-600 text-blue-600"
            />
            <span class="text-sm text-gray-400">Enable</span>
          </label>
        </div>

        <div v-if="queueEnabled" class="space-y-4">
          <!-- Queue Mode Selection -->
          <div class="bg-gray-700/50 rounded-lg p-4">
            <label class="text-sm text-gray-400 block mb-2">Queue Mode</label>
            <div class="flex gap-2">
              <button
                @click="updateSetting('queue_mode', 'smart')"
                class="flex-1 px-4 py-2 rounded-lg font-medium transition-colors"
                :class="queueMode === 'smart' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-600'"
              >
                Smart Mode
              </button>
              <button
                @click="updateSetting('queue_mode', 'manual')"
                class="flex-1 px-4 py-2 rounded-lg font-medium transition-colors"
                :class="queueMode === 'manual' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-600'"
              >
                Manual Mode
              </button>
            </div>
          </div>

          <!-- Smart Mode Settings -->
          <div v-if="queueMode === 'smart'" class="space-y-4">
            <div class="text-sm text-gray-400 font-medium">Smart Mode Settings</div>

            <!-- Main Base Mode -->
            <div class="bg-gray-700/50 rounded-lg p-4">
              <label class="text-sm text-gray-400 block mb-2">Main Base Mode</label>
              <select
                :value="smartMainMode"
                @change="updateSmartModeConfig('main_base_mode', $event.target.value)"
                class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
              >
                <option v-for="mode in mainBaseModes" :key="mode" :value="mode">{{ mode }}</option>
              </select>
              <p class="text-xs text-gray-500 mt-1">Mode to use for main base farming</p>
            </div>

            <!-- BB Gold Troop Mode -->
            <div class="bg-gray-700/50 rounded-lg p-4">
              <label class="text-sm text-gray-400 block mb-2">BB Gold Troop Mode</label>
              <select
                :value="smartBBGoldMode"
                @change="updateSmartModeConfig('bb_gold_mode', $event.target.value)"
                class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
              >
                <option v-for="option in bbGoldTroopModeOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
              <p class="text-xs text-gray-500 mt-1">Troop composition for Builder Base attacks</p>
            </div>

            <!-- Storage Thresholds -->
            <div class="bg-gray-700/50 rounded-lg p-4">
              <label class="text-sm text-gray-400 block mb-3">Switch to BB when storages reach:</label>
              <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <div>
                  <label class="text-xs text-gray-500 block mb-1">Gold %</label>
                  <input
                    type="number"
                    :value="smartGoldThreshold"
                    @input="updateSmartModeConfig('storage_targets.gold_threshold', parseInt($event.target.value) || 100)"
                    min="0"
                    max="100"
                    class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label class="text-xs text-gray-500 block mb-1">Elixir %</label>
                  <input
                    type="number"
                    :value="smartElixirThreshold"
                    @input="updateSmartModeConfig('storage_targets.elixir_threshold', parseInt($event.target.value) || 100)"
                    min="0"
                    max="100"
                    class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div class="col-span-2 sm:col-span-1">
                  <label class="text-xs text-gray-500 block mb-1">DE % (if enabled)</label>
                  <input
                    type="number"
                    :value="smartDEThreshold"
                    @input="updateSmartModeConfig('storage_targets.de_threshold', parseInt($event.target.value) || 100)"
                    min="0"
                    max="100"
                    :disabled="!smartWaitForDE"
                    class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none disabled:opacity-50"
                  />
                </div>
              </div>
              <label class="flex items-center gap-2 mt-3 cursor-pointer">
                <input
                  type="checkbox"
                  :checked="smartWaitForDE"
                  @change="updateSmartModeConfig('storage_targets.wait_for_de', $event.target.checked)"
                  class="w-4 h-4 rounded border-gray-600 text-blue-600"
                />
                <span class="text-sm text-gray-400">Also wait for Dark Elixir</span>
              </label>
            </div>

            <!-- After BB Behavior -->
            <div class="bg-gray-700/50 rounded-lg p-4">
              <label class="text-sm text-gray-400 block mb-2">After BB storages full:</label>
              <div class="flex gap-2">
                <button
                  @click="updateSmartModeConfig('after_bb_behavior', 'stop')"
                  class="flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                  :class="smartAfterBB === 'stop' ? 'bg-red-600/80 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-600'"
                >
                  Stop Bot
                </button>
                <button
                  @click="updateSmartModeConfig('after_bb_behavior', 'achievement_farm')"
                  class="flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                  :class="smartAfterBB === 'achievement_farm' ? 'bg-yellow-600/80 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-600'"
                >
                  Achievement Farm
                </button>
              </div>
              <div v-if="smartAfterBB === 'achievement_farm'" class="mt-3">
                <label class="text-xs text-gray-500 block mb-1">Achievement Farm duration (minutes)</label>
                <input
                  type="number"
                  :value="achievementDuration"
                  @input="updateAchievementConfig('duration_minutes', parseInt($event.target.value) || 20)"
                  min="1"
                  max="120"
                  class="w-24 bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
            </div>
          </div>

          <!-- Manual Mode Info -->
          <div v-else class="bg-gray-700/50 rounded-lg p-4">
            <div class="text-sm text-gray-400 font-medium mb-2">Manual Mode</div>
            <p class="text-xs text-gray-500">
              Manual mode schedule configuration is available in the Tkinter GUI.
              Define custom task sequences with time or storage-based conditions.
            </p>
          </div>
        </div>
      </div>
    </CollapsibleSection>

    <!-- Achievement Building Priority -->
    <CollapsibleSection v-if="showAchievementOptions" title="Achievement Building Priority" icon="🏆" :defaultOpen="false">
      <div class="space-y-4">
        <p class="text-xs text-gray-500">
          Drag to reorder priority. Higher buildings are scanned/targeted first.
          Toggle checkbox to enable/disable scanning for each building.
        </p>

        <!-- Priority List -->
        <div class="space-y-2">
          <div
            v-for="(building, index) in achievementPriorityList"
            :key="building"
            draggable="true"
            @dragstart="onDragStart(index)"
            @dragover="onDragOver($event, index)"
            @drop="onDrop(index)"
            @dragend="onDragEnd"
            class="flex items-center gap-3 p-3 bg-gray-700/50 rounded-lg cursor-move transition-all"
            :class="{
              'opacity-50': draggedIndex === index,
              'border-2 border-blue-500': draggedIndex !== null && draggedIndex !== index
            }"
          >
            <!-- Drag Handle -->
            <div class="text-gray-500 hover:text-gray-300">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8h16M4 16h16" />
              </svg>
            </div>

            <!-- Priority Number -->
            <span class="w-6 h-6 flex items-center justify-center bg-gray-600 rounded text-xs font-bold text-gray-300">
              {{ index + 1 }}
            </span>

            <!-- Enable/Disable Checkbox -->
            <input
              type="checkbox"
              :checked="buildingScanSettings[building]"
              @change="toggleBuildingScan(building)"
              @click.stop
              class="w-5 h-5 rounded border-gray-600 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
            />

            <!-- Building Name -->
            <span class="flex-1 text-white text-sm" :class="{ 'text-gray-500 line-through': !buildingScanSettings[building] }">
              {{ buildingDisplayNames[building] || building }}
            </span>

            <!-- Move Buttons (for touch/accessibility) -->
            <div class="flex gap-1">
              <button
                @click.stop="movePriorityUp(index)"
                :disabled="index === 0"
                class="p-1.5 rounded hover:bg-gray-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
                </svg>
              </button>
              <button
                @click.stop="movePriorityDown(index)"
                :disabled="index === achievementPriorityList.length - 1"
                class="p-1.5 rounded hover:bg-gray-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- Reset Button -->
        <button
          @click="resetPriorityList"
          class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg text-sm transition-colors"
        >
          Reset to Default Order
        </button>
      </div>
    </CollapsibleSection>

    <!-- Global Settings -->
    <CollapsibleSection title="Global Settings" icon="⚙️" :defaultOpen="false">
      <div class="space-y-3">
        <!-- Reinforcements -->
        <label class="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg cursor-pointer hover:bg-gray-700 transition-colors">
          <div>
            <span class="text-white">Reinforcements</span>
            <p class="text-xs text-gray-500">Request and use clan castle troops</p>
          </div>
          <input
            type="checkbox"
            :checked="reinforcementsEnabled"
            @change="updateSetting('reinforcements_enabled', $event.target.checked)"
            class="w-5 h-5 rounded border-gray-600 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
          />
        </label>

        <!-- Skip on TH Detection Fail -->
        <label class="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg cursor-pointer hover:bg-gray-700 transition-colors">
          <div>
            <span class="text-white">Skip on TH Detection Fail</span>
            <p class="text-xs text-gray-500">Skip base if town hall cannot be detected</p>
          </div>
          <input
            type="checkbox"
            :checked="skipOnTHFail"
            @change="updateSetting('skip_on_th_fail', $event.target.checked)"
            class="w-5 h-5 rounded border-gray-600 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
          />
        </label>

        <!-- Detection Overlay -->
        <div class="bg-gray-700/50 rounded-lg p-3 space-y-3">
          <label class="flex items-center justify-between cursor-pointer">
            <div>
              <span class="text-white">Detection Overlay</span>
              <p class="text-xs text-gray-500">Show transparent overlay with CV detections</p>
            </div>
            <input
              type="checkbox"
              :checked="overlayEnabled"
              @change="updateSetting('overlay_enabled', $event.target.checked)"
              class="w-5 h-5 rounded border-gray-600 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
            />
          </label>

          <!-- Hide Low Confidence - shown when overlay is enabled -->
          <label v-if="overlayEnabled" class="flex items-center justify-between cursor-pointer pl-4 border-l-2 border-gray-600">
            <div>
              <span class="text-white text-sm">Hide Low Confidence</span>
              <p class="text-xs text-gray-500">Hide red rectangles (low confidence detections)</p>
            </div>
            <input
              type="checkbox"
              :checked="overlayHideLowConf"
              @change="updateSetting('overlay_hide_low_conf', $event.target.checked)"
              class="w-5 h-5 rounded border-gray-600 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
            />
          </label>
        </div>

        <!-- Parallel Scanning -->
        <label class="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg cursor-pointer hover:bg-gray-700 transition-colors">
          <div>
            <span class="text-white">Parallel Scanning</span>
            <p class="text-xs text-gray-500">Use multi-threading for faster building detection</p>
          </div>
          <input
            type="checkbox"
            :checked="parallelScanning"
            @change="updateSetting('parallel_scanning', $event.target.checked)"
            class="w-5 h-5 rounded border-gray-600 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
          />
        </label>

        <!-- GPU Scanning -->
        <label class="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg cursor-pointer hover:bg-gray-700 transition-colors">
          <div>
            <span class="text-white">GPU Scanning (WIP)</span>
            <p class="text-xs text-gray-500 text-yellow-500">Experimental - issues with some buildings</p>
          </div>
          <input
            type="checkbox"
            :checked="gpuScanning"
            @change="updateSetting('gpu_scanning', $event.target.checked)"
            class="w-5 h-5 rounded border-gray-600 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
          />
        </label>

        <!-- Auto Pause -->
        <label class="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg cursor-pointer hover:bg-gray-700 transition-colors">
          <div>
            <span class="text-white">Auto Pause Enabled</span>
            <p class="text-xs text-gray-500">Enable automatic break system</p>
          </div>
          <input
            type="checkbox"
            :checked="autoPauseEnabled"
            @change="updateSetting('auto_pause_enabled', $event.target.checked)"
            class="w-5 h-5 rounded border-gray-600 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
          />
        </label>

        <!-- Break Settings -->
        <div v-if="autoPauseEnabled" class="grid grid-cols-2 gap-3">
          <div class="bg-gray-700/50 rounded-lg p-3">
            <label class="text-xs text-gray-500 block mb-1">Break Interval (min)</label>
            <input
              type="number"
              :value="breakInterval"
              @input="updateSetting('break_interval', parseInt($event.target.value) || 60)"
              min="15"
              max="120"
              class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div class="bg-gray-700/50 rounded-lg p-3">
            <label class="text-xs text-gray-500 block mb-1">Break Duration (min)</label>
            <input
              type="number"
              :value="breakDuration"
              @input="updateSetting('break_duration', parseInt($event.target.value) || 5)"
              min="1"
              max="30"
              class="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
        </div>

        <!-- BB Collect Interval -->
        <div class="bg-gray-700/50 rounded-lg p-3">
          <label class="text-xs text-gray-500 block mb-1">BB Collect Interval (attacks)</label>
          <input
            type="number"
            :value="bbCollectInterval"
            @input="updateSetting('bb_collect_interval', parseInt($event.target.value) || 12)"
            min="1"
            max="50"
            class="w-full sm:w-32 bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
          />
          <p class="text-xs text-gray-500 mt-1">Collect loot every N BB Gold attacks</p>
        </div>
      </div>
    </CollapsibleSection>

    <!-- Current Profile Info -->
    <div class="bg-gray-800 rounded-xl border border-gray-700 p-3 md:p-4">
      <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
        <div>
          <div class="text-xs md:text-sm text-gray-500">Active Profile</div>
          <div class="text-base md:text-lg font-medium text-white">{{ profile }}</div>
        </div>
        <div class="px-3 py-1 bg-green-600/20 text-green-400 rounded-lg text-xs md:text-sm">
          Settings synced with Tkinter GUI
        </div>
      </div>
    </div>
  </div>
</template>
