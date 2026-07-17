<script setup>
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

function logout() {
  auth.logout()
  router.push('/login')
}

const navItems = [
  { label: '工作台', path: '/dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
]
</script>

<template>
  <div class="min-h-screen flex" style="background: oklch(0.975 0.005 105)">
    <!-- Sidebar -->
    <aside class="w-56 flex-shrink-0 flex flex-col p-4" style="background: oklch(0.97 0.005 105 / 0.6); backdrop-filter: blur(20px); border-right: 1px solid oklch(0 0 0 / 0.05)">
      <!-- Logo -->
      <div class="flex items-center gap-2.5 px-3 mb-8 mt-1">
        <div class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style="background: oklch(0.58 0.11 105)">
          <svg width="16" height="16" viewBox="0 0 32 32" fill="none"><path d="M7 10h18M7 16h12M7 22h8" stroke="#fff" stroke-width="2" stroke-linecap="round"/></svg>
        </div>
        <span class="font-semibold text-sm tracking-tight" style="color: oklch(0.35 0.008 105)">视频分镜分析</span>
      </div>

      <!-- Nav -->
      <nav class="flex-1 space-y-1">
        <router-link
          v-for="item in navItems" :key="item.path"
          :to="item.path"
          class="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150"
          :class="route.path === item.path ? '' : ''"
          :style="route.path === item.path
            ? { background: 'oklch(0.58 0.11 105 / 0.1)', color: 'oklch(0.50 0.115 105)' }
            : { color: 'oklch(0.48 0.008 105)', background: 'transparent' }"
        >
          <svg class="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" :d="item.icon"/>
          </svg>
          {{ item.label }}
        </router-link>
      </nav>

      <!-- User -->
      <div class="pt-4 border-t" style="border-color: oklch(0 0 0 / 0.06)">
        <div class="flex items-center gap-3 px-3 py-2">
          <div class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold text-white" style="background: oklch(0.62 0.165 60)">
            {{ auth.user?.username?.charAt(0)?.toUpperCase() || 'U' }}
          </div>
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium truncate" style="color: oklch(0.35 0.008 105)">{{ auth.user?.username || '用户' }}</div>
            <div class="text-xs" style="color: oklch(0.68 0.005 105)">剪辑师</div>
          </div>
          <button
            @click="logout"
            class="p-1.5 rounded-lg transition-colors duration-150 hover:bg-red-50"
            style="color: oklch(0.68 0.005 105)"
            title="退出登录"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
            </svg>
          </button>
        </div>
      </div>
    </aside>

    <!-- Main content -->
    <main class="flex-1 p-8 overflow-auto">
      <slot />
    </main>
  </div>
</template>
