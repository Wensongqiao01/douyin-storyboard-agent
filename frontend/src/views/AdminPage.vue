<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { api } from '../api/client'
import AppLayout from '../components/AppLayout.vue'

const router = useRouter()
const message = useMessage()
const users = ref([])
const loading = ref(true)
const showCreate = ref(false)
const newUser = ref({ username: '', password: '', is_admin: false })
const submitting = ref(false)

const user = JSON.parse(localStorage.getItem('user') || '{}')
if (!user.is_admin) {
  router.replace('/')
}

async function loadUsers() {
  loading.value = true
  try {
    users.value = await api.listUsers()
  } catch (err) {
    message.error(err.message)
  } finally {
    loading.value = false
  }
}

async function createUser() {
  if (!newUser.value.username.trim() || !newUser.value.password.trim()) return
  if (newUser.value.password.length < 6) {
    message.warning('密码至少6位')
    return
  }
  submitting.value = true
  try {
    await api.createUser(newUser.value.username.trim(), newUser.value.password, newUser.value.is_admin)
    message.success('用户创建成功')
    showCreate.value = false
    newUser.value = { username: '', password: '', is_admin: false }
    await loadUsers()
  } catch (err) {
    message.error(err.message)
  } finally {
    submitting.value = false
  }
}

async function deleteUser(u) {
  if (!window.confirm(`确定删除用户「${u.username}」？`)) return
  try {
    await api.deleteUser(u.id)
    message.success('已删除')
    await loadUsers()
  } catch (err) {
    message.error(err.message)
  }
}

function formatDuration(s) {
  if (!s) return '--'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}

onMounted(loadUsers)
</script>

<template>
  <AppLayout>
    <div class="flex items-center justify-between mb-8">
      <div>
        <h1 class="text-2xl font-semibold tracking-tight" style="color: oklch(0.15 0.008 105)">用户管理</h1>
        <p class="text-sm mt-1" style="color: oklch(0.48 0.008 105)">管理账号与查看使用情况</p>
      </div>
      <button
        @click="showCreate = true"
        class="px-5 py-2.5 rounded-xl text-sm font-semibold text-white transition-all duration-200 hover:shadow-md active:scale-[0.98]"
        style="background: oklch(0.58 0.11 105)"
      >
        新建用户
      </button>
    </div>

    <!-- Create modal -->
    <div v-if="showCreate" class="fixed inset-0 z-50 flex items-center justify-center p-6" style="background: oklch(0 0 0 / 0.3); backdrop-filter: blur(4px)">
      <div class="glass-strong rounded-3xl p-8 w-full max-w-md shadow-xl" @click.stop>
        <h3 class="text-lg font-semibold mb-6" style="color: oklch(0.15 0.008 105)">新建用户</h3>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium mb-1.5" style="color: oklch(0.35 0.008 105)">用户名</label>
            <input v-model="newUser.username" class="w-full px-4 py-2.5 rounded-xl text-sm outline-none" style="background: oklch(0.97 0.005 105); border: 1px solid oklch(0 0 0 / 0.08)" placeholder="输入用户名">
          </div>
          <div>
            <label class="block text-sm font-medium mb-1.5" style="color: oklch(0.35 0.008 105)">密码</label>
            <input v-model="newUser.password" type="password" class="w-full px-4 py-2.5 rounded-xl text-sm outline-none" style="background: oklch(0.97 0.005 105); border: 1px solid oklch(0 0 0 / 0.08)" placeholder="至少6位">
          </div>
          <label class="flex items-center gap-2 cursor-pointer">
            <input v-model="newUser.is_admin" type="checkbox" class="w-4 h-4 rounded">
            <span class="text-sm" style="color: oklch(0.35 0.008 105)">设为管理员</span>
          </label>
        </div>
        <div class="flex justify-end gap-3 mt-6">
          <button @click="showCreate = false" class="px-5 py-2.5 rounded-xl text-sm font-medium" style="background: oklch(0.96 0.005 105); color: oklch(0.48 0.008 105)">取消</button>
          <button @click="createUser" :disabled="submitting" class="px-5 py-2.5 rounded-xl text-sm font-semibold text-white transition-all duration-200 disabled:opacity-50" style="background: oklch(0.58 0.11 105)">
            {{ submitting ? '创建中...' : '创建' }}
          </button>
        </div>
      </div>
    </div>

    <!-- User table -->
    <div v-if="loading" class="text-center py-20 text-sm" style="color: oklch(0.68 0.005 105)">加载中...</div>
    <div v-else class="glass rounded-2xl overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr style="background: oklch(0.96 0.005 105)">
            <th class="text-left px-5 py-3 font-medium" style="color: oklch(0.48 0.008 105)">用户名</th>
            <th class="text-left px-5 py-3 font-medium" style="color: oklch(0.48 0.008 105)">角色</th>
            <th class="text-center px-5 py-3 font-medium" style="color: oklch(0.48 0.008 105)">总任务</th>
            <th class="text-center px-5 py-3 font-medium" style="color: oklch(0.48 0.008 105)">已完成</th>
            <th class="text-center px-5 py-3 font-medium" style="color: oklch(0.48 0.008 105)">总时长</th>
            <th class="text-left px-5 py-3 font-medium" style="color: oklch(0.48 0.008 105)">创建时间</th>
            <th class="text-center px-5 py-3 font-medium" style="color: oklch(0.48 0.008 105)">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id" class="border-t" style="border-color: oklch(0 0 0 / 0.06)">
            <td class="px-5 py-3 font-medium" style="color: oklch(0.15 0.008 105)">{{ u.username }}</td>
            <td class="px-5 py-3">
              <span class="text-xs px-2 py-0.5 rounded-full font-medium" :style="{ background: u.is_admin ? 'oklch(0.62 0.165 60 / 0.15)' : 'oklch(0.62 0.16 220 / 0.1)', color: u.is_admin ? 'oklch(0.62 0.165 60)' : 'oklch(0.62 0.16 220)' }">
                {{ u.is_admin ? '管理员' : '普通用户' }}
              </span>
            </td>
            <td class="px-5 py-3 text-center" style="color: oklch(0.35 0.008 105)">{{ u.task_count }}</td>
            <td class="px-5 py-3 text-center" style="color: oklch(0.58 0.16 160)">{{ u.done_count }}</td>
            <td class="px-5 py-3 text-center" style="color: oklch(0.35 0.008 105)">{{ formatDuration(u.total_duration) }}</td>
            <td class="px-5 py-3 text-xs" style="color: oklch(0.68 0.005 105)">{{ u.created_at }}</td>
            <td class="px-5 py-3 text-center">
              <button
                @click="deleteUser(u)"
                class="text-xs px-2 py-1 rounded-lg transition-colors duration-150 hover:bg-red-50"
                style="color: oklch(0.52 0.20 25)"
              >删除</button>
            </td>
          </tr>
          <tr v-if="users.length === 0">
            <td colspan="7" class="text-center py-12" style="color: oklch(0.68 0.005 105)">暂无用户</td>
          </tr>
        </tbody>
      </table>
    </div>
  </AppLayout>
</template>
