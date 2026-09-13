<script setup>
import { ref } from 'vue'

const props = defineProps({
  title: {
    type: String,
    required: true
  },
  icon: {
    type: String,
    default: ''
  },
  defaultOpen: {
    type: Boolean,
    default: false
  }
})

const isOpen = ref(props.defaultOpen)

function toggle() {
  isOpen.value = !isOpen.value
}
</script>

<template>
  <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
    <!-- Header -->
    <button
      @click="toggle"
      class="w-full flex items-center justify-between p-4 hover:bg-gray-750 transition-colors"
    >
      <div class="flex items-center gap-3">
        <span v-if="icon" class="text-xl">{{ icon }}</span>
        <h3 class="text-lg font-semibold text-white">{{ title }}</h3>
      </div>
      <svg
        class="w-5 h-5 text-gray-400 transition-transform duration-200"
        :class="{ 'rotate-180': isOpen }"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <!-- Content -->
    <div
      class="overflow-hidden transition-all duration-200"
      :class="isOpen ? 'max-h-[2000px] opacity-100' : 'max-h-0 opacity-0'"
    >
      <div class="p-4 pt-0 border-t border-gray-700">
        <slot />
      </div>
    </div>
  </div>
</template>
