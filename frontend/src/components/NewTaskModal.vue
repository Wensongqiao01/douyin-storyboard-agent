<script setup>
import { ref, onUnmounted } from 'vue'
import { useMessage } from 'naive-ui'
import { api } from '../api/client'

const emit = defineEmits(['close', 'created'])
const message = useMessage()
const url = ref('')
const submitted = ref(false)
const currentStep = ref(0)
const errorMsg = ref('')
const elapsed = ref([0, 0, 0, 0])
let es = null
let tick = null

const steps = [
  { key: 'download', label: '下载视频', icon: 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4' },
  { key: 'transcribe', label: '语音转写', icon: 'M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m2-4a2 2 0 01-2-2V6a2 2 0 012-2h4a2 2 0 012 2v8a2 2 0 01-2 2h-4z' },
  { key: 'segment', label: '语义分镜', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01' },
  { key: 'done', label: '完成', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
]

// 后端状态 → 步骤索引
const STATUS_STEP = {
  pending: 0, downloading: 0,
  transcribing: 1,
  detecting: 2, segmenting: 2, fusing: 2,
  done: 3,
}

async function submit() {
  if (!url.value.trim()) return
  submitted.value = true
  errorMsg.value = ''
  try {
    const { task_id } = await api.createTask(url.value.trim())
    tick = setInterval(() => { elapsed.value[currentStep.value]++ }, 1000)
    es = new EventSource(api.streamUrl(task_id))
    es.onmessage = (ev) => {
      const { status } = JSON.parse(ev.data)
      if (status === 'error') {
        errorMsg.value = '分析失败，请检查链接是否有效'
        cleanup()
        return
      }
      currentStep.value = STATUS_STEP[status] ?? currentStep.value
      if (status === 'done') {
        cleanup()
        emit('created', task_id)
      }
    }
    es.onerror = () => {
      // SSE 断开（如服务重启）：不报错，提示用户到列表查看
      cleanup()
      emit('created', task_id)
    }
  } catch (err) {
    submitted.value = false
    message.error(err.message)
  }
}

function cleanup() {
  if (es) { es.close(); es = null }
  if (tick) { clearInterval(tick); tick = null }
}

function formatElapsed(s) {
  if (!s) return ''
  const m = Math.floor(s / 60)
  const sec = s % 60
  return m > 0 ? `${m}分${sec}秒` : `${sec}秒`
}

onUnmounted(cleanup)
</script>

<template>
  <!-- Backdrop -->
  <div class="fixed inset-0 z-50 flex items-center justify-center p-6" style="background: oklch(0 0 0 / 0.3); backdrop-filter: blur(4px)" @click.self="!submitted && emit('close')">
    <!-- Modal -->
    <div class="glass-strong rounded-3xl p-8 w-full max-w-lg shadow-xl" @click.stop>
      <div v-if="!submitted">
        <h3 class="text-lg font-semibold mb-6" style="color: oklch(0.15 0.008 105)">新建分析任务</h3>
        <label class="block text-sm font-medium mb-2" style="color: oklch(0.35 0.008 105)">视频链接</label>
        <textarea
          v-model="url"
          placeholder="粘贴抖音视频链接..."
          rows="3"
          class="w-full px-4 py-3 rounded-xl text-[15px] outline-none transition-all duration-200 focus:ring-2 resize-none"
          style="background: oklch(0.97 0.005 105); border: 1px solid oklch(0 0 0 / 0.08); color: oklch(0.15 0.008 105)"
        ></textarea>
        <div class="flex justify-end gap-3 mt-6">
          <button
            @click="emit('close')"
            class="px-5 py-2.5 rounded-xl text-sm font-medium transition-all duration-150"
            style="background: oklch(0.96 0.005 105); color: oklch(0.48 0.008 105)"
          >
            取消
          </button>
          <button
            @click="submit"
            :disabled="!url.trim()"
            class="px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 hover:shadow-md active:scale-[0.98] disabled:opacity-50"
            style="background: oklch(0.58 0.11 105); color: #fff"
          >
            开始分析
          </button>
        </div>
      </div>

      <!-- Progress -->
      <div v-else>
        <h3 class="text-lg font-semibold mb-8" style="color: oklch(0.15 0.008 105)">正在分析...</h3>
        <div class="space-y-1">
          <div
            v-for="(step, i) in steps" :key="step.key"
            class="flex items-center gap-4 py-3 px-4 rounded-xl transition-all duration-300"
            :style="{
              background: i <= currentStep ? 'oklch(0.58 0.11 105 / 0.06)' : 'transparent',
            }"
          >
            <!-- Step icon -->
            <div
              class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 transition-all duration-300"
              :style="{
                background: i < currentStep ? 'oklch(0.58 0.16 160)' : i === currentStep ? 'oklch(0.58 0.11 105)' : 'oklch(0.96 0.005 105)',
                color: i <= currentStep ? '#fff' : 'oklch(0.68 0.005 105)',
              }"
            >
              <svg v-if="i < currentStep" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
              <svg v-else-if="i === currentStep" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
              <svg v-else class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" :d="step.icon"/></svg>
            </div>
            <!-- Step label -->
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium" :style="{ color: i <= currentStep ? 'oklch(0.35 0.008 105)' : 'oklch(0.68 0.005 105)' }">{{ step.label }}</div>
            </div>
            <!-- Elapsed -->
            <div class="text-xs flex-shrink-0" style="color: oklch(0.68 0.005 105)">
              {{ i < currentStep ? '完成' : i === currentStep ? formatElapsed(elapsed[i]) || '进行中...' : '' }}
            </div>
          </div>
        </div>
        <p v-if="errorMsg" class="text-center text-sm mt-4" style="color: oklch(0.52 0.20 25)">
          {{ errorMsg }}
          <button class="underline ml-2" @click="emit('close')">关闭</button>
        </p>
        <p class="text-center text-xs mt-6" style="color: oklch(0.68 0.005 105)">请耐心等待，通常需要 5-10 分钟</p>
      </div>
    </div>
  </div>
</template>
