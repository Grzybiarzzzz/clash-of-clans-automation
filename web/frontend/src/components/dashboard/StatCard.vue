<script setup>
defineProps({
  title: String,
  value: [String, Number],
  icon: String,
  color: {
    type: String,
    default: 'blue'
  }
})

const colorClasses = {
  blue: 'from-blue-500 to-blue-600',
  green: 'from-green-500 to-green-600',
  yellow: 'from-yellow-500 to-yellow-600',
  purple: 'from-purple-500 to-purple-600',
  pink: 'from-pink-500 to-pink-600'
}
</script>

<template>
  <div class="bg-gray-800 rounded-xl p-3 md:p-4 border border-gray-700">
    <div class="flex items-center justify-between mb-2">
      <span class="text-gray-400 text-xs md:text-sm">{{ title }}</span>
      <span class="text-xl md:text-2xl">{{ icon }}</span>
    </div>
    <div
      class="text-lg md:text-2xl font-bold bg-gradient-to-r bg-clip-text text-transparent"
      :class="colorClasses[color]"
    >
      {{ value }}
    </div>
  </div>
</template>
