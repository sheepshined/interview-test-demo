<template>
  <div>
    <TopNav back-text="返回首页" />
    <main style="max-width:700px;margin:0 auto;padding:48px 24px;">
      <h1 style="font-size:24px;font-weight:600;color:var(--text-primary);margin-bottom:8px;">选择面试配置</h1>
      <p style="font-size:14px;color:var(--text-muted);margin-bottom:32px;">选择目标岗位和面试题量</p>

      <div class="ds-card" style="padding:28px;">
        <div style="margin-bottom:28px;">
          <label style="display:block;font-size:14px;font-weight:600;margin-bottom:12px;color:var(--text-primary);">岗位类别</label>

          <div v-if="loadingRoles" style="padding:18px 0;color:var(--text-muted);font-size:13px;">正在加载岗位…</div>
          <div v-else-if="roleError" class="load-error">
            <span>{{ roleError }}</span>
            <button class="ds-btn ds-btn-outline" style="padding:6px 14px;font-size:12px;" @click="loadRoles">重新加载</button>
          </div>
          <div v-else style="display:flex;flex-wrap:wrap;gap:8px;">
            <button v-for="role in roles" :key="role.key" type="button" class="chip" :class="{active:selectedRole===role.key}" @click="selectedRole=role.key">
              {{ role.title }}
            </button>
          </div>
        </div>

        <div>
          <label style="display:block;font-size:14px;font-weight:600;margin-bottom:12px;color:var(--text-primary);">面试题量</label>
          <div style="display:flex;gap:10px;flex-wrap:wrap;">
            <button v-for="count in countOptions" :key="count.value" type="button" class="count-btn" :class="{active:questionCount===count.value}" @click="questionCount=count.value">
              {{ count.label }}
            </button>
          </div>
        </div>
      </div>

      <button class="ds-btn ds-btn-primary w-full" style="padding:14px;margin-top:24px;" @click="startInterview" :disabled="loadingRoles || !selectedRole">
        {{ loadingRoles ? '岗位加载中…' : '开始面试 →' }}
      </button>
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getRoles } from '../api'
import TopNav from '../components/TopNav.vue'

const router = useRouter()
const CONFIG_KEY = 'interviewConfig'
const roles = ref([])
const selectedRole = ref('')
const questionCount = ref(5)
const loadingRoles = ref(false)
const roleError = ref('')
const countOptions = [
  { value: 5, label: '5 题 (约10分钟)' },
  { value: 10, label: '10 题 (约20分钟)' },
  { value: 15, label: '15 题 (约30分钟)' },
]

function loadSavedConfig() {
  try { return JSON.parse(localStorage.getItem(CONFIG_KEY) || 'null') } catch (_) { return null }
}

async function loadRoles() {
  loadingRoles.value = true
  roleError.value = ''
  roles.value = []
  try {
    const result = await getRoles()
    if (!result.success) {
      roleError.value = result.message || '岗位加载失败'
      return
    }
    if (!Array.isArray(result.roles) || result.roles.length === 0) {
      roleError.value = '后端未返回可用岗位，请检查题库配置'
      return
    }
    roles.value = result.roles
    // 默认回显上次选择的岗位与题量, 不必每次重选
    const saved = loadSavedConfig()
    selectedRole.value = (saved && roles.value.some(r => r.key === saved.key))
      ? saved.key
      : result.roles[0].key
    if (saved && countOptions.some(c => c.value === saved.questionCount)) {
      questionCount.value = saved.questionCount
    }
  } finally {
    loadingRoles.value = false
  }
}

function startInterview() {
  const role = roles.value.find((item) => item.key === selectedRole.value)
  if (!role) {
    roleError.value = '请先选择一个岗位'
    return
  }
  const config = {
    key: role.key,
    title: role.title,
    resumeContext: '',
    resumeSkills: [],
    questionCount: questionCount.value,
  }
  // sessionStorage 供本次跳转使用; localStorage 记住配置, 刷新/重进免重选
  sessionStorage.setItem('selectedRole', JSON.stringify(config))
  localStorage.setItem(CONFIG_KEY, JSON.stringify(config))
  router.push('/interview')
}

onMounted(loadRoles)
</script>

<style scoped>
.chip { padding:8px 18px;border-radius:999px;font-size:13px;cursor:pointer;border:1px solid var(--border-default);background:var(--surface);color:var(--text-secondary);transition:all .16s; }
.chip.active { background:var(--brand-900);color:var(--brand-50);border-color:var(--brand-900); }
.count-btn { padding:10px 18px;border:1px solid var(--border-default);border-radius:var(--radius-md);background:var(--surface);color:var(--text-secondary);font-size:13px;cursor:pointer;transition:all .16s; }
.count-btn.active { background:var(--brand-900);color:var(--brand-50);border-color:var(--brand-900); }
.load-error { display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;border:1px solid rgba(220,38,38,.2);border-radius:var(--radius-md);background:rgba(220,38,38,.06);color:var(--error);font-size:13px; }
</style>
