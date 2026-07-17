<script setup>
import { NConfigProvider, NMessageProvider, darkTheme } from 'naive-ui'
import { useAuthStore } from './stores/auth'
import { computed } from 'vue'

const auth = useAuthStore()
const themeOverrides = {
  common: {
    primaryColor: '#8B9A3D',
    primaryColorHover: '#7A8935',
    borderRadius: '10px',
    fontFamily: "'Noto Sans SC', system-ui, -apple-system, sans-serif",
  },
}
</script>

<template>
  <NConfigProvider :theme-overrides="themeOverrides">
    <NMessageProvider>
      <router-view />
    </NMessageProvider>
  </NConfigProvider>
</template>
