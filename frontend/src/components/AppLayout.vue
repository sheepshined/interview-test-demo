<template>
  <div class="app-shell">
    <aside class="side-nav" :class="{ collapsed }">
      <div class="side-head">
        <div class="brand" :title="'AI 模拟面试官'">
          <span class="brand-mark">面</span>
          <span v-if="!collapsed" class="brand-name">AI 模拟面试官</span>
        </div>
        <button class="side-collapse-btn" :title="collapsed ? '展开侧边栏' : '收起侧边栏'" @click="collapsed = !collapsed">
          <DSIcon :name="collapsed ? 'chevron-right' : 'chevron-left'" :size="16" />
        </button>
      </div>

      <nav class="side-groups">
        <div class="side-group">
          <div v-if="!collapsed" class="side-group-title">面试流程</div>
          <router-link to="/" class="side-link" :class="{ active: $route.path === '/' }" title="首页">
            <DSIcon name="house" :size="18" />
            <span v-if="!collapsed" class="side-text">首页</span>
          </router-link>
          <router-link to="/resume-upload" class="side-link" :class="{ active: $route.path === '/resume-upload' }" title="简历匹配">
            <DSIcon name="file" :size="18" />
            <span v-if="!collapsed" class="side-text">简历匹配</span>
          </router-link>
          <router-link to="/choose-job" class="side-link" :class="{ active: $route.path === '/choose-job' }" title="选择岗位">
            <DSIcon name="map-pin" :size="18" />
            <span v-if="!collapsed" class="side-text">选择岗位</span>
          </router-link>
          <router-link to="/interview-records" class="side-link" :class="{ active: $route.path === '/interview-records' }" title="面试记录">
            <DSIcon name="file-text" :size="18" />
            <span v-if="!collapsed" class="side-text">面试记录</span>
          </router-link>
        </div>

        <div class="side-group">
          <div v-if="!collapsed" class="side-group-title">个人知识库</div>
          <router-link to="/knowledge" class="side-link" :class="{ active: ($route.path === '/knowledge' || $route.path.startsWith('/knowledge/')) && $route.path !== '/knowledge/graph' && $route.path !== '/knowledge/chat' }" title="我的笔记">
            <DSIcon name="pen-line" :size="18" />
            <span v-if="!collapsed" class="side-text">我的笔记</span>
          </router-link>
          <router-link to="/knowledge/graph" class="side-link" :class="{ active: $route.path === '/knowledge/graph' }" title="知识图谱">
            <DSIcon name="grip" :size="18" />
            <span v-if="!collapsed" class="side-text">知识图谱</span>
          </router-link>
          <router-link to="/knowledge/chat" class="side-link" :class="{ active: $route.path === '/knowledge/chat' }" title="AI 对话">
            <DSIcon name="message-circle" :size="18" />
            <span v-if="!collapsed" class="side-text">AI 对话</span>
          </router-link>
        </div>
      </nav>

      <div class="side-foot">
        <div class="side-user">
          <span class="side-avatar">{{ username.charAt(0).toUpperCase() }}</span>
          <span v-if="!collapsed" class="side-username">{{ username }}</span>
        </div>
        <button v-if="!collapsed" class="side-logout" title="退出登录" @click="handleLogout">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2v10" />
            <path d="M18.4 6.6a9 9 0 1 1-12.77.04" />
          </svg>
        </button>
      </div>
    </aside>

    <main class="app-main">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { clearAuth, getUsername } from '../auth'
import DSIcon from './DSIcon.vue'

const router = useRouter()
const username = getUsername()
const collapsed = ref(false)

function handleLogout() {
  clearAuth()
  router.push('/login')
}
</script>

<style scoped>
.app-shell {
  display: flex;
  /* 固定视口: 文档本身不滚动, 滚动交给 .app-main 内部容器,
     保证滚轮在所有页面都可用 */
  height: 100vh;
  overflow: hidden;
  background: var(--bg-100);
}

.side-nav {
  width: 216px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border-right: 1px solid var(--border-default);
  position: sticky;
  top: 0;
  height: 100vh;
  transition: width 0.22s var(--ease-out);
  overflow: hidden;
}

.side-nav.collapsed {
  width: 64px;
}

.side-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 14px 14px;
  border-bottom: 1px solid var(--border-default);
  white-space: nowrap;
}

.collapsed .side-head {
  flex-direction: column;
  padding: 14px 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.brand-mark {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: var(--brand-800);
  color: #fff;
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.12);
}

.brand-name {
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.01em;
}

.side-collapse-btn {
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  padding: 5px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background var(--dur-fast) ease, color var(--dur-fast) ease;
}

.side-collapse-btn:hover {
  background: var(--surface-raised);
  color: var(--text-primary);
}

.side-groups {
  flex: 1;
  padding: 12px 10px;
  overflow-y: auto;
}

.side-group {
  margin-bottom: 18px;
}

.side-group-title {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--text-faint);
  text-transform: uppercase;
  padding: 0 10px 6px;
  white-space: nowrap;
}

.side-link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  margin-bottom: 2px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  white-space: nowrap;
  position: relative;
  transition: background var(--dur-fast) ease, color var(--dur-fast) ease;
}

.side-link :deep(svg) {
  flex-shrink: 0;
  opacity: 0.85;
}

.side-link:hover {
  background: var(--surface-raised);
  color: var(--text-primary);
}

.side-link:hover :deep(svg) { opacity: 1; }

.side-link.active {
  background: var(--brand-100);
  color: var(--brand-800);
  font-weight: 600;
}

.side-link.active :deep(svg) { opacity: 1; }

.side-link.active::before {
  content: '';
  position: absolute;
  left: -10px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 18px;
  border-radius: 0 3px 3px 0;
  background: var(--accent-500);
}

.collapsed .side-link {
  justify-content: center;
  padding: 10px 0;
}

.side-text {
  overflow: hidden;
  text-overflow: ellipsis;
}

.side-foot {
  border-top: 1px solid var(--border-default);
  padding: 12px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  white-space: nowrap;
}

.collapsed .side-foot {
  flex-direction: column;
  padding: 12px 0;
  gap: 10px;
}

.side-user {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.collapsed .side-user {
  justify-content: center;
}

.side-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--brand-800);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.side-username {
  font-size: 13px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
}

.side-logout {
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  padding: 6px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background var(--dur-fast) ease, color var(--dur-fast) ease;
}

.side-logout:hover {
  background: var(--error-bg);
  color: var(--error);
}

.app-main {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
}
</style>
