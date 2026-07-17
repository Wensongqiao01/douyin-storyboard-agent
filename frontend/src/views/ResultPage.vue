<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import AppLayout from '../components/AppLayout.vue'
import TimelineBar from '../components/TimelineBar.vue'
import SceneCard from '../components/SceneCard.vue'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const taskId = route.params.id
const currentIndex = ref(-1)

// Mock result data
const taskResult = ref({
  task_id: taskId,
  title: '产品发布会亮点回顾',
  url: 'https://v.douyin.com/abc123/',
  status: 'done',
  video_path: '',
  scenes: [
    { index: 0, start_time: 0, end_time: 25.5, summary: '开场：主持人介绍发布会主题', text: '各位来宾大家好，欢迎来到我们2026年夏季新品发布会。今天我们将为大家带来三款重磅产品...', has_scene_cut: true },
    { index: 1, start_time: 25.5, end_time: 58.2, summary: '产品一：智能手表功能演示', text: '首先是我们的新一代智能手表。这款手表采用了全新的钛合金表壳，重量仅为上一代的60%...', has_scene_cut: true },
    { index: 2, start_time: 58.2, end_time: 95.0, summary: '产品二：无线耳机技术亮点', text: '接下来是我们的旗舰无线耳机。这款耳机搭载了我们自研的芯片，降噪深度达到55分贝...', has_scene_cut: false },
    { index: 3, start_time: 95.0, end_time: 132.8, summary: '产品三：折叠屏手机压轴', text: '最后压轴的是大家期待已久的折叠屏手机。我们采用了全新的铰链设计，实现了无缝折叠...', has_scene_cut: true },
    { index: 4, start_time: 132.8, end_time: 186.0, summary: '结尾：发布会总结与上市时间', text: '以上就是今天发布会的全部内容。三款产品都将在下个月1号正式开售，欢迎大家到官网预约...', has_scene_cut: false },
  ],
})

const totalDuration = computed(() => {
  const scenes = taskResult.value.scenes
  if (!scenes.length) return 0
  return scenes[scenes.length - 1].end_time - scenes[0].start_time
})

function selectScene(index) {
  currentIndex.value = index
  const card = document.getElementById(`scene-${index}`)
  if (card) {
    card.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

function highlightTimeline(index) {
  currentIndex.value = index
}

function formatTime(s) {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

function exportFormat(format) {
  const labels = { srt: 'SRT 字幕', md: 'Markdown', csv: 'CSV', clips: '视频片段' }
  message.info(`正在导出 ${labels[format]}...`)
}

function downloadVideo() {
  message.info('正在准备视频下载...')
}

function backToDashboard() {
  router.push('/dashboard')
}
</script>

<template>
  <AppLayout>
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

    <!-- Video player area -->
    <div class="glass rounded-2xl overflow-hidden mb-6">
      <div class="aspect-video flex items-center justify-center" style="background: oklch(0.12 0.005 105)">
        <div class="text-center">
          <svg class="w-16 h-16 mx-auto mb-3" style="color: oklch(0.58 0.11 105)" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1"><path stroke-linecap="round" stroke-linejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path stroke-linecap="round" stroke-linejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          <p style="color: oklch(0.68 0.005 105)" class="text-sm">视频播放器</p>
          <p class="text-xs mt-1" style="color: oklch(0.55 0.005 105)">部署后端后即可播放视频，支持 HTTP Range 拖动定位</p>
        </div>
      </div>
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
  </AppLayout>
</template>
