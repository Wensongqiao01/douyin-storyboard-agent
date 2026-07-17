<script setup>
import { computed } from 'vue'

const props = defineProps({
  scenes: { type: Array, default: () => [] },
  currentIndex: { type: Number, default: -1 },
  totalDuration: { type: Number, default: 0 },
})

const emit = defineEmits(['select'])

const segments = computed(() => {
  if (!props.totalDuration) return []
  return props.scenes.map((s, i) => ({
    left: (s.start_time / props.totalDuration) * 100,
    width: Math.max(((s.end_time - s.start_time) / props.totalDuration) * 100, 1),
    hasCut: s.has_scene_cut,
    index: i,
  }))
})

function formatTime(s) {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}
</script>

<template>
  <div v-if="scenes.length" class="w-full">
    <!-- Time labels -->
    <div class="flex justify-between text-xs mb-2 px-1" style="color: oklch(0.68 0.005 105)">
      <span>00:00</span>
      <span>{{ formatTime(totalDuration) }}</span>
    </div>
    <!-- Track -->
    <div class="relative h-10 rounded-xl overflow-hidden cursor-pointer" style="background: oklch(0.94 0.01 105)">
      <div
        v-for="seg in segments" :key="seg.index"
        class="absolute top-0 h-full transition-all duration-200 hover:brightness-95"
        :class="seg.index === currentIndex ? 'ring-2 ring-inset' : ''"
        :style="{
          left: seg.left + '%',
          width: seg.width + '%',
          background: seg.index === currentIndex
            ? 'oklch(0.58 0.11 105)'
            : seg.index % 2 === 0 ? 'oklch(0.62 0.165 60 / 0.5)' : 'oklch(0.62 0.12 80 / 0.4)',
          '--tw-ring-color': 'oklch(1 0 0)',
        }"
        @click="emit('select', seg.index)"
      >
        <!-- Cut marker -->
        <div
          v-if="seg.hasCut && seg.index > 0"
          class="absolute left-0 top-0 bottom-0 w-0.5"
          style="background: oklch(1 0 0 / 0.6)"
        ></div>
      </div>
    </div>
    <!-- Legend -->
    <div class="flex items-center gap-4 mt-2 text-xs" style="color: oklch(0.68 0.005 105)">
      <span>{{ scenes.length }} 个分镜</span>
      <span>·</span>
      <span>总时长 {{ formatTime(totalDuration) }}</span>
    </div>
  </div>
</template>
