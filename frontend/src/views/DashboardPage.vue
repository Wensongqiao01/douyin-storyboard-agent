<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useMessage } from 'naive-ui'
import NewTaskModal from '../components/NewTaskModal.vue'
import AppLayout from '../components/AppLayout.vue'

const router = useRouter()
const auth = useAuthStore()
const message = useMessage()

const searchQuery = ref('')
const statusFilter = ref('all')
const showNewTask = ref(false)

// Mock task data
const tasks = ref([
  { id: '1', url: 'https://v.douyin.com/abc123/', title: '产品发布会亮点回顾', status: 'done', scenes: 8, duration: 186, createdAt: '2026-07-15 14:30', videoPath: '' },
  { id: '2', url: 'https://v.douyin.com/def456/', title: '用户访谈精华剪辑', status: 'processing', scenes: 0, duration: 0, createdAt: '2026-07-15 15:20', videoPath: '' },
  { id: '3', url: 'https://v.douyin.com/ghi789/', title: '新品开箱第一视角', status: 'error', scenes: 0, duration: 0, createdAt: '2026-07-14 10:15', videoPath: '' },
  { id: '4', url: 'https://v.douyin.com/jkl012/', title: '幕后花絮合集', status: 'done', scenes: 12, duration: 245, createdAt: '2026-07-14 09:00', videoPath: '' },
])

const statusLabel = { done: '已完成', processing: '处理中', error: '失败', pending: '排队中' }
const statusColor = { done: 'oklch(0.58 0.16 160)', processing: 'oklch(0.62 0.165 60)', error: 'oklch(0.52 0.20 25)', pending: 'oklch(0.68 0.005 105)' }

const filteredTasks = computed(() => {
  return tasks.value.filter(t => {
    const matchStatus = statusFilter.value === 'all' || t.status === statusFilter.value
    const matchSearch = !searchQuery.value || t.title.includes(searchQuery.value) || t.url.includes(searchQuery.value)
    return matchStatus && matchSearch
  })
})

function formatDuration(s) {
  if (!s) return '--'
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}:${String(sec).padStart(2, '0')}`
}

function viewResult(task) {
  if (task.status === 'done') {
    router.push(`/result/${task.id}`)
  }
}

function deleteTask(task) {
  tasks.value = tasks.value.filter(t => t.id !== task.id)
  message.success('任务已删除')
}

function onTaskCreated(taskId) {
  showNewTask.value = false
  tasks.value.unshift({
    id: taskId,
    url: '',
    title: '新任务',
    status: 'processing',
    scenes: 0,
    duration: 0,
    createdAt: new Date().toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-'),
    videoPath: '',
  })
}
</script>

<template>
  <AppLayout>
    <!-- Header -->
    <div class="flex items-center justify-between mb-8">
      <div>
        <h1 class="text-2xl font-semibold tracking-tight" style="color: oklch(0.15 0.008 105)">工作台</h1>
        <p class="text-sm mt-1" style="color: oklch(0.48 0.008 105)">管理和查看视频分镜分析任务</p>
      </div>
      <button
        @click="showNewTask = true"
        class="px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 hover:shadow-md active:scale-[0.98]"
        style="background: oklch(0.58 0.11 105); color: #fff"
      >
        新建任务
      </button>
    </div>

    <!-- Filters -->
    <div class="flex items-center gap-3 mb-6">
      <div class="relative flex-1 max-w-xs">
        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style="color: oklch(0.68 0.005 105)" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索任务..."
          class="w-full pl-10 pr-4 py-2.5 rounded-xl text-sm outline-none transition-all duration-200 focus:ring-2"
          style="background: oklch(0.97 0.005 105); border: 1px solid oklch(0 0 0 / 0.06); color: oklch(0.15 0.008 105)"
        />
      </div>
      <select
        v-model="statusFilter"
        class="px-4 py-2.5 rounded-xl text-sm outline-none cursor-pointer"
        style="background: oklch(0.97 0.005 105); border: 1px solid oklch(0 0 0 / 0.06); color: oklch(0.35 0.008 105)"
      >
        <option value="all">全部状态</option>
        <option value="done">已完成</option>
        <option value="processing">处理中</option>
        <option value="error">失败</option>
      </select>
    </div>

    <!-- Task list -->
    <div v-if="filteredTasks.length === 0" class="text-center py-20">
      <div class="text-4xl mb-4">📭</div>
      <p class="text-lg font-medium" style="color: oklch(0.35 0.008 105)">暂无任务</p>
      <p class="text-sm mt-1" style="color: oklch(0.68 0.005 105)">点击"新建任务"开始分析你的第一条视频</p>
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="task in filteredTasks" :key="task.id"
        @click="viewResult(task)"
        class="glass rounded-2xl p-5 transition-all duration-200 cursor-pointer"
        :class="task.status === 'done' ? 'hover:shadow-md hover:scale-[1.005]' : ''"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-4 min-w-0">
            <!-- Status dot -->
            <div class="w-2.5 h-2.5 rounded-full flex-shrink-0" :style="{ background: statusColor[task.status] }"></div>
            <!-- Info -->
            <div class="min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-[15px] font-medium truncate" style="color: oklch(0.15 0.008 105)">{{ task.title || '未命名任务' }}</span>
                <span class="text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0" :style="{ background: statusColor[task.status] + '20', color: statusColor[task.status] }">
                  {{ statusLabel[task.status] }}
                </span>
              </div>
              <div class="flex items-center gap-4 text-xs" style="color: oklch(0.68 0.005 105)">
                <span>{{ task.createdAt }}</span>
                <span v-if="task.scenes">{{ task.scenes }} 个分镜</span>
                <span v-if="task.duration">时长 {{ formatDuration(task.duration) }}</span>
              </div>
            </div>
          </div>
          <!-- Actions -->
          <div class="flex items-center gap-2 flex-shrink-0 ml-4">
            <span v-if="task.status === 'done'" class="text-xs font-medium" style="color: oklch(0.58 0.11 105)">查看结果 →</span>
            <button
              @click.stop="deleteTask(task)"
              class="p-2 rounded-lg text-xs transition-colors duration-150 hover:bg-red-50"
              style="color: oklch(0.68 0.005 105)"
              title="删除"
            >
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- New Task Modal -->
    <NewTaskModal v-if="showNewTask" @close="showNewTask = false" @created="onTaskCreated" />
  </AppLayout>
</template>
