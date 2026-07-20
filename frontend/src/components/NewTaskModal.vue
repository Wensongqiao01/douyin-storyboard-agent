<script setup>
import { ref } from 'vue'
import { useMessage } from 'naive-ui'
import { api } from '../api/client'

const emit = defineEmits(['close', 'created'])
const message = useMessage()
const url = ref('')
const batchMode = ref(false)
const submitting = ref(false)

async function submit() {
  const text = url.value.trim()
  if (!text) return
  submitting.value = true

  try {
    if (batchMode.value) {
      await api.createBatch(text)
      message.success('批量任务已提交')
    } else {
      await api.createTask(text)
      message.success('任务已提交')
    }
    emit('created')
  } catch (err) {
    message.error(err.message)
    submitting.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center p-6" style="background: oklch(0 0 0 / 0.3); backdrop-filter: blur(4px)">
    <div class="glass-strong rounded-3xl p-8 w-full max-w-lg shadow-xl" @click.stop>
      <div class="flex items-center justify-between mb-6">
        <h3 class="text-lg font-semibold" style="color: oklch(0.15 0.008 105)">新建分析任务</h3>
        <div class="flex rounded-lg p-0.5 text-xs font-medium" style="background: oklch(0.96 0.005 105)">
          <button :class="!batchMode ? 'shadow-sm' : ''" @click="batchMode = false"
            class="px-3 py-1.5 rounded-md transition-all"
            :style="{ background: !batchMode ? '#fff' : 'transparent', color: !batchMode ? 'oklch(0.35 0.008 105)' : 'oklch(0.58 0.005 105)' }">单条</button>
          <button :class="batchMode ? 'shadow-sm' : ''" @click="batchMode = true"
            class="px-3 py-1.5 rounded-md transition-all"
            :style="{ background: batchMode ? '#fff' : 'transparent', color: batchMode ? 'oklch(0.35 0.008 105)' : 'oklch(0.58 0.005 105)' }">批量</button>
        </div>
      </div>
      <label class="block text-sm font-medium mb-2" style="color: oklch(0.35 0.008 105)">{{ batchMode ? '批量链接（每行一个）' : '视频链接' }}</label>
      <textarea
        v-model="url"
        :placeholder="batchMode ? '每行粘贴一个抖音分享链接...' : '粘贴抖音分享文案或链接，自动提取视频 URL...'"
        :rows="batchMode ? 6 : 3"
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
          :disabled="!url.trim() || submitting"
          class="px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 hover:shadow-md active:scale-[0.98] disabled:opacity-50"
          style="background: oklch(0.58 0.11 105); color: #fff"
        >
          {{ submitting ? '提交中...' : '开始分析' }}
        </button>
      </div>
    </div>
  </div>
</template>
