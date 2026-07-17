<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

const features = [
  { title: '智能分镜', desc: 'AI 语义理解视频内容，自动识别话题转换点，精准切分每一个镜头段落。', icon: '🎬' },
  { title: '时间轴定位', desc: '精确到秒的时间戳标注，每条分镜对应视频中的起止位置，支持一键跳转。', icon: '⏱️' },
  { title: '一键导出', desc: '支持 SRT 字幕、Markdown 文稿、CSV 表格、视频片段切割，直接导入剪辑工具。', icon: '📤' },
]
</script>

<template>
  <div class="bg-landing min-h-screen flex flex-col">
    <!-- Nav -->
    <nav class="flex items-center justify-between px-8 py-5 max-w-6xl mx-auto w-full">
      <div class="flex items-center gap-2.5">
        <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background: oklch(0.58 0.11 105)">
          <svg width="18" height="18" viewBox="0 0 32 32" fill="none"><path d="M7 10h18M7 16h12M7 22h8" stroke="#fff" stroke-width="2" stroke-linecap="round"/></svg>
        </div>
        <span class="font-semibold text-[15px]" style="font-family: var(--lp-font-body); font-weight: 500; color: oklch(0.50 0.115 105)">视频分镜分析</span>
      </div>
      <button
        @click="router.push('/login')"
        class="px-5 py-2.5 rounded-full text-sm font-medium transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
        style="background: oklch(0.62 0.165 60); color: #fff; font-family: var(--lp-font-body);"
      >
        开始使用
      </button>
    </nav>

    <!-- Hero -->
    <section class="flex-1 flex flex-col items-center justify-center px-6 pt-12 pb-24 text-center max-w-3xl mx-auto">
      <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs mb-8"
        style="background: oklch(0.62 0.165 60 / 0.12); color: oklch(0.54 0.155 58); font-family: var(--lp-font-body);">
        <span class="w-1.5 h-1.5 rounded-full" style="background: oklch(0.62 0.165 60)"></span>
        抖音视频智能分析工具
      </div>
      <h1
        class="mb-6"
        style="font-family: var(--lp-font-display); font-weight: 600; font-size: clamp(2.5rem, 5vw, 3.5rem); line-height: 1.3; letter-spacing: 0.02em; color: oklch(0.15 0.008 105); text-wrap: balance;"
      >
        把视频变成分镜稿<br />只需要一条链接
      </h1>
      <p
        class="mb-12 max-w-lg"
        style="font-family: var(--lp-font-body); font-weight: 400; font-size: 1.1rem; line-height: 1.7; color: oklch(0.48 0.008 105);"
      >
        粘贴抖音视频链接，AI 自动完成下载、转写、语义分镜，输出带精确时间戳的结构化分镜稿，直接导入剪辑软件。
      </p>
      <button
        @click="router.push('/login')"
        class="px-8 py-3.5 rounded-full text-[15px] font-semibold transition-all duration-200 hover:shadow-lg hover:shadow-amber-500/20 hover:scale-[1.02] active:scale-[0.98]"
        style="background: oklch(0.62 0.165 60); color: #fff; font-family: var(--lp-font-body);"
      >
        开始使用
      </button>
    </section>

    <!-- Features -->
    <section class="px-6 pb-24 max-w-5xl mx-auto w-full">
      <div class="grid gap-6" style="grid-template-columns: repeat(auto-fit, minmax(280px, 1fr))">
        <div
          v-for="(f, i) in features" :key="i"
          class="rounded-2xl p-8 transition-all duration-200 hover:scale-[1.01]"
          style="background: oklch(1 0 0 / 0.7); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border: 1px solid oklch(0 0 0 / 0.06);"
        >
          <div class="text-2xl mb-4">{{ f.icon }}</div>
          <h3 class="text-[17px] font-semibold mb-2" style="font-family: var(--lp-font-body); color: oklch(0.15 0.008 105)">{{ f.title }}</h3>
          <p class="text-[14px] leading-relaxed" style="font-family: var(--lp-font-body); color: oklch(0.48 0.008 105)">{{ f.desc }}</p>
        </div>
      </div>
    </section>

    <!-- Footer -->
    <footer class="px-6 py-8 text-center text-xs" style="color: oklch(0.68 0.005 105); font-family: var(--lp-font-body);">
      视频分镜分析 &middot; 内部工具
    </footer>
  </div>
</template>
