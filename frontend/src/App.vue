<template>
  <div id="app-root">
    <AppLayout v-if="showSidebar" />
    <router-view v-else v-slot="{ Component }">
      <transition name="page" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from './components/AppLayout.vue'

const route = useRoute()
// 登录页无侧边栏; 其余页面统一 AppLayout (侧边栏 + 内容区, v0.7)
const showSidebar = computed(() => route.name !== 'Login')
</script>
