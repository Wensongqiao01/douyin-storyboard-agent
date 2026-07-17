<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { api } from '../api/client'
import AppLayout from '../components/AppLayout.vue'
import TimelineBar from '../components/TimelineBar.vue'
import SceneCard from '../components/SceneCard.vue'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const taskId = route.params.id
const currentIndex = ref(-1)
const loading = ref(true)
const videoEl = ref(null)
const taskResult = ref({ title: '', url: '', status: '', scenes: [] })

onMounted(async () => {
  try {
    const data = await api.getTask(taskId)
    taskResult.value = {
      title: data.title || '未命名任务',
      url: data.url,
      status: data.status,
      scenes: data.scenes_detail || [],
    }
  } catch (err) {
    message.error(err.message)
    router.push('/dashboard')
  } finally {
    loading.value = false
  }
})

const videoSrc = api.videoUrl(taskId)

const totalDuration = computed(() => {
  const scenes = taskResult.value.scenes
  if (!scenes.length) return 0
  return scenes[scenes.length - 1].end_time - scenes[0].start_time
})

function selectScene(index) {
  currentIndex.value = index
  const scene = taskResult.value.scenes[index]
  if (videoEl.value && scene) {
    videoEl.value.currentTime = scene.start_time
    videoEl.value.play().catch(() => {})
  }
  const card = document.getElementById(`scene-${index}`)
  if (card) card.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function highlightTimeline(index) {
  currentIndex.value = index
  const scene = taskResult.value.scenes[index]
  if (videoEl.value && scene) {
    videoEl.value.currentTime = scene.start_time
  }
}

function formatTime(s) {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

function exportFormat(format) {
  window.open(api.exportUrl(taskId, format), '_blank')
}

function downloadVideo() {
  window.open(api.videoUrl(taskId), '_blank')
}

function backToDashboard() {
  router.push('/dashboard')
}
</script>

<template>
  <AppLayout>
    <!-- Loading state -->
    <div v-if="loading" class="flex items-center justify-center py-32">
      <p style="color: oklch(0.68 0.005 105)" class="text-sm">正在加载分镜结果...</p>
    </div>

    <!-- Content -->
    <template v-else>
      <!-- Top bar -->
      <div class="flex items-center justify-between mb-6">
        <div class="flex items-center gap-4">
          <button
            @click="backToDashboard"
            class="p-2 rounded-xl transition-colors duration-150"
            style="color: oklch(0.48 0.008 105)"
          >
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18"/></svg>
          </button>
          <div>
            <h1 class="text-xl font-semibold tracking-tight" style="color: oklch(0.15 0.008 105)">{{ taskResult.title }}</h1>
            <p class="text-xs mt-0.5" style="color: oklch(0.68 0.005 105)">{{ taskResult.scenes.length }} 个分镜 · 总时长 {{ formatTime(totalDuration) }}</p>
          </div>
        </div>
        <!-- Export buttons -->
        <div class="flex items-center gap-2">
          <button @click="downloadVideo()" class="px-4 py-2 rounded-xl text-sm font-medium transition-all duration-150" style="background: oklch(0.96 0.005 105); color: oklch(0.48 0.008 105)">
            <span class="flex items-center gap-1.5">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
              视频
            </span>
          </button>
          <div class="relative group">
            <button class="px-4 py-2 rounded-xl text-sm font-semibold transition-all duration-150 flex items-center gap-1.5" style="background: oklch(0.58 0.11 105); color: #fff">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
              导出
            </button>
            <div class="absolute right-0 top-full mt-1 rounded-xl py-1.5 shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-150 z-10 min-w-[140px]"
              style="background: oklch(1 0 0); border: 1px solid oklch(0 0 0 / 0.08)">
              <button @click="exportFormat('srt')" class="block w-full text-left px-4 py-2 text-sm hover:bg-brand-50 transition-colors" style="color: oklch(0.35 0.008 105)">SRT 字幕</button>
              <button @click="exportFormat('md')" class="block w-full text-left px-4 py-2 text-sm hover:bg-brand-50 transition-colors" style="color: oklch(0.35 0.008 105)">Markdown</button>
              <button @click="exportFormat('csv')" class="block w-full text-left px-4 py-2 text-sm hover:bg-brand-50 transition-colors" style="color: oklch(0.35 0.008 105)">CSV 表格</button>
              <div class="border-t my-1" style="border-color: oklch(0 0 0 / 0.06)"></div>
              <button @click="exportFormat('clips')" class="block w-full text-left px-4 py-2 text-sm hover:bg-brand-50 transition-colors" style="color: oklch(0.35 0.008 105)">视频片段</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Real video player -->
      <div class="glass rounded-2xl overflow-hidden mb-6">
        <video
          ref="videoEl"
          :src="videoSrc"
          controls
          class="w-full aspect-video"
          style="background: oklch(0.12 0.005 105)"
        ></video>
      </div>

      <!-- Timeline -->
      <div class="mb-8">
        <TimelineBar
          :scenes="taskResult.scenes"
          :currentIndex="currentIndex"
          :totalDuration="totalDuration"
          @select="selectScene"
        />
      </div>

      <!-- Scene cards -->
      <div class="space-y-3">
        <SceneCard
          v-for="(scene, i) in taskResult.scenes"
          :key="scene.index"
          :id="`scene-${i}`"
          :scene="scene"
          :active="currentIndex === i"
          @click="highlightTimeline(i)"
        />
      </div>
    </template>
  </AppLayout>
</template>
