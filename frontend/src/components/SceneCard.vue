<script setup>
defineProps({
  scene: { type: Object, required: true },
  active: { type: Boolean, default: false },
})

function formatTime(s) {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}
</script>

<template>
  <div
    class="glass rounded-2xl p-5 transition-all duration-200"
    :class="active ? 'ring-2' : ''"
    :style="{
      '--tw-ring-color': active ? 'oklch(0.58 0.11 105)' : 'transparent',
      transform: active ? 'scale(1.01)' : 'scale(1)',
    }"
  >
    <!-- Header -->
    <div class="flex items-center gap-3 mb-3">
      <span class="text-sm font-bold flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center text-white"
        style="background: oklch(0.58 0.11 105)">
        {{ scene.index + 1 }}
      </span>
      <span class="text-[15px] font-semibold flex-1" style="color: oklch(0.15 0.008 105)">{{ scene.summary }}</span>
      <span class="text-xs flex-shrink-0 px-2 py-1 rounded-full font-medium"
        style="background: oklch(0.58 0.11 105 / 0.08); color: oklch(0.50 0.115 105)">
        {{ formatTime(scene.start_time) }} - {{ formatTime(scene.end_time) }}
      </span>
    </div>
    <!-- Text -->
    <p class="text-sm leading-relaxed" style="color: oklch(0.48 0.008 105)">{{ scene.text }}</p>
    <!-- Cut badge -->
    <div v-if="scene.has_scene_cut" class="mt-3 flex items-center gap-1.5">
      <div class="w-1.5 h-1.5 rounded-full" style="background: oklch(0.62 0.165 60)"></div>
      <span class="text-xs" style="color: oklch(0.62 0.165 60)">画面切点</span>
    </div>
  </div>
</template>
