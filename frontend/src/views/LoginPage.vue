<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useMessage } from 'naive-ui'

const router = useRouter()
const auth = useAuthStore()
const message = useMessage()

const username = ref('')
const password = ref('')
const loading = ref(false)

async function handleLogin() {
  if (!username.value || !password.value) {
    message.warning('请输入账号和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    message.success('登录成功')
    router.push('/dashboard')
  } catch (e) {
    message.error(e.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="bg-landing min-h-screen flex items-center justify-center px-6">
    <div
      class="glass-strong rounded-3xl p-10 w-full max-w-sm shadow-sm"
      style="box-shadow: 0 4px 32px oklch(0 0 0 / 0.04), 0 1px 2px oklch(0 0 0 / 0.04)"
    >
      <!-- Logo -->
      <div class="text-center mb-8">
        <div class="w-10 h-10 rounded-xl flex items-center justify-center mx-auto mb-4" style="background: oklch(0.58 0.11 105)">
          <svg width="20" height="20" viewBox="0 0 32 32" fill="none"><path d="M7 10h18M7 16h12M7 22h8" stroke="#fff" stroke-width="2" stroke-linecap="round"/></svg>
        </div>
        <h2 class="text-xl font-semibold tracking-tight" style="color: oklch(0.15 0.008 105)">登录</h2>
        <p class="text-sm mt-1.5" style="color: oklch(0.48 0.008 105)">视频分镜分析工具</p>
      </div>

      <!-- Form -->
      <form @submit.prevent="handleLogin" class="space-y-4">
        <div>
          <label class="block text-sm font-medium mb-1.5" style="color: oklch(0.35 0.008 105)">账号</label>
          <input
            v-model="username"
            type="text"
            placeholder="输入账号"
            class="w-full px-4 py-3 rounded-xl text-[15px] outline-none transition-all duration-200 focus:ring-2"
            style="background: oklch(0.97 0.005 105); border: 1px solid oklch(0 0 0 / 0.08); color: oklch(0.15 0.008 105)"
            :style="{ '--tw-ring-color': 'oklch(0.58 0.11 105 / 0.3)' }"
          />
        </div>
        <div>
          <label class="block text-sm font-medium mb-1.5" style="color: oklch(0.35 0.008 105)">密码</label>
          <input
            v-model="password"
            type="password"
            placeholder="输入密码"
            class="w-full px-4 py-3 rounded-xl text-[15px] outline-none transition-all duration-200 focus:ring-2"
            style="background: oklch(0.97 0.005 105); border: 1px solid oklch(0 0 0 / 0.08); color: oklch(0.15 0.008 105)"
            :style="{ '--tw-ring-color': 'oklch(0.58 0.11 105 / 0.3)' }"
            @keyup.enter="handleLogin"
          />
        </div>
        <button
          type="submit"
          :disabled="loading"
          class="w-full py-3 rounded-xl text-[15px] font-semibold transition-all duration-200 hover:shadow-md active:scale-[0.98] disabled:opacity-60"
          style="background: oklch(0.58 0.11 105); color: #fff"
        >
          {{ loading ? '登录中...' : '登 录' }}
        </button>
      </form>

      <p class="text-center text-xs mt-6" style="color: oklch(0.68 0.005 105)">
        仅限内部使用 &middot; 联系管理员获取账号
      </p>
    </div>
  </div>
</template>
