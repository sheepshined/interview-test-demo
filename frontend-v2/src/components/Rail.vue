<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Icon from './Icon.vue'
import { clearAuth, getUsername } from '../auth'

const route = useRoute()
const router = useRouter()
const username = getUsername()
const activePage = computed(() => route.meta.page || '')

const GROUPS = [
  {
    title: 'Interview / 面试流程',
    links: [
      { page: 'home', href: '/', idx: '01', ic: 'house', label: '首页' },
      { page: 'resume', href: '/resume-upload', idx: '02', ic: 'file', label: '简历匹配' },
      { page: 'choose', href: '/choose-job', idx: '03', ic: 'pin', label: '选择岗位' },
      { page: 'records', href: '/interview-records', idx: '04', ic: 'records', label: '面试记录' },
    ],
  },
  {
    title: 'Library / 个人知识库',
    links: [
      { page: 'workspace', href: '/knowledge', idx: '05', ic: 'pen', label: '我的笔记' },
      { page: 'graph', href: '/knowledge/graph', idx: '06', ic: 'graph', label: '知识图谱' },
      { page: 'chat', href: '/knowledge/chat', idx: '07', ic: 'chat', label: 'AI 对话' },
    ],
  },
]

function logout() {
  clearAuth()
  router.push('/login')
}
</script>

<template>
  <aside class="rail">
    <div class="rail-head">
      <RouterLink class="brandmark" to="/">
        <span class="seal">面</span>
        <span>
          <span class="name">AI 模拟面试官</span>
          <span class="sub" style="display:block">Interview Studio</span>
        </span>
      </RouterLink>
    </div>

    <nav class="rail-groups">
      <div v-for="g in GROUPS" :key="g.title" class="rail-group">
        <div class="rail-group-title">{{ g.title }}</div>
        <RouterLink
          v-for="l in g.links" :key="l.page" :to="l.href"
          class="rail-link" :class="{ 'is-active': activePage === l.page }"
        >
          <span class="idx">{{ l.idx }}</span>
          <Icon :name="l.ic" /><span>{{ l.label }}</span>
        </RouterLink>
      </div>
    </nav>

    <div class="rail-foot">
      <span class="rail-avatar">{{ (username || 'U').charAt(0).toUpperCase() }}</span>
      <div class="rail-user">
        <div class="u-name">{{ username || '未登录' }}</div>
        <div class="u-role">Candidate</div>
      </div>
      <button class="rail-quit" title="退出登录" @click="logout"><Icon name="arrowLeft" /></button>
    </div>
  </aside>
</template>