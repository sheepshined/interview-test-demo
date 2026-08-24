<template>
  <nav class="ds-navbar">
    <div class="ds-navbar-inner">
      <div class="flex items-center gap-3">
        <span v-if="backText" @click="$router.go(-1)" class="ds-navbar-link flex items-center gap-1 cursor-pointer" style="color: var(--text-muted);">
          <span class="hide-mobile">{{ backText }}</span>
        </span>
        <span class="ds-navbar-logo">AI模拟面试官</span>
      </div>
      <div class="flex items-center gap-1 hide-mobile">
        <router-link to="/" class="ds-navbar-link" :class="{ active: $route.path === '/' }">首页</router-link>
        <router-link to="/resume-upload" class="ds-navbar-link" :class="{ active: $route.path === '/resume-upload' }">简历匹配</router-link>
        <router-link to="/choose-job" class="ds-navbar-link" :class="{ active: $route.path === '/choose-job' }">选择岗位</router-link>
      </div>
      <div class="flex items-center gap-3">
        <span class="text-sm hide-mobile" style="color: var(--text-muted);">{{ username }}</span>
        <button @click="handleLogout" class="ds-btn ds-btn-ghost" style="padding: 4px 10px; font-size: 12px;">退出</button>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { clearAuth, getUsername } from '../auth'
defineProps({ backText: { type: String, default: '' } })
const router = useRouter()
const username = getUsername()
function handleLogout() { clearAuth(); router.push('/login') }
</script>
