<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { api } from '../api/client'
import NewTaskModal from '../components/NewTaskModal.vue'
import AppLayout from '../components/AppLayout.vue'

const router = useRouter()
const message = useMessage()

const searchQuery = ref('')
const statusFilter = ref('all')
const showNewTask = ref(false)
const tasks = ref([])
const loading = ref(true)

// 后端细分状态归并为前端 4 类
const PROCESSING = ['downloading', 'transcribing', 'detecting', 'segmenting', 'fusing']
function displayStatus(s) {
  if (PROCESSING.includes(s)) return 'processing'
  return s // pending / done / error
}

const statusLabel = { done: '已完成', processing: '处理中', error: '失败', pending: '排队中' }
const statusColor = { done: 'oklch(0.58 0.16 160)', processing: 'oklch(0.62 0.165 60)', error: 'oklch(0.52 0.20 25)', pending: 'oklch(0.68 0.005 105)' }

async function loadTasks() {
  loading.value = true
  try {
    tasks.value = await api.listTasks()
  } catch (err) {
    message.error(err.message)
  } finally {
    loading.value = false
  }
}
onMounted(loadTasks)

const filteredTasks = computed(() => {
  return tasks.value.filter(t => {
    const ds = displayStatus(t.status)
    const matchStatus = statusFilter.value === 'all' || ds === statusFilter.value
    const matchSearch = !searchQuery.value || (t.title || '').includes(searchQuery.value) || t.url.includes(searchQuery.value)
    return matchStatus && matchSearch
  })
})

function formatDuration(s) {
  if (!s) return '--'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}

function viewResult(task) {
  if (task.status === 'done') router.push(`/result/${task.id}`)
}

async function deleteTask(task) {
  try {
    await api.deleteTask(task.id)
    tasks.value = tasks.value.filter(t => t.id !== task.id)
    message.success('任务已删除')
  } catch (err) {
    message.error(err.message)
  }
}

function onTaskCreated() {
  showNewTask.value = false
  loadTasks()
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
    <div v-if="loading" class="text-center py-20 text-sm" style="color: oklch(0.68 0.005 105)">加载中...</div>
    <div v-else-if="filteredTasks.length === 0" class="text-center py-20">
      <div class="text-4xl mb-4">📭</div>
      <p class="text-lg font-medium" style="color: oklch(0.35 0.008 105)">暂无任务</p>
      <p class="text-sm mt-1" style="color: oklch(0.68 0.005 105)">点击"新建任务"开始分析你的第一条视频</p>
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="task in filteredTasks" :key="task.id"
        @click="viewResult(task)"
        class="glass rounded-2xl p-5 transition-all duration-200 cursor-pointer"
        :class="displayStatus(task.status) === 'done' ? 'hover:shadow-md hover:scale-[1.005]' : ''"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-4 min-w-0">
            <!-- Status dot -->
            <div class="w-2.5 h-2.5 rounded-full flex-shrink-0" :style="{ background: statusColor[displayStatus(task.status)] }"></div>
            <!-- Info -->
            <div class="min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-[15px] font-medium truncate" style="color: oklch(0.15 0.008 105)">{{ task.title || '未命名任务' }}</span>
                <span class="text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0" :style="{ background: statusColor[displayStatus(task.status)] + '20', color: statusColor[displayStatus(task.status)] }">
                  {{ statusLabel[displayStatus(task.status)] }}
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
            <span v-if="displayStatus(task.status) === 'done'" class="text-xs font-medium" style="color: oklch(0.58 0.11 105)">查看结果 →</span>
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
