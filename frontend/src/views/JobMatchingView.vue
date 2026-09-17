<template>
  <div>
    <TopNav back-text="返回上传" />
    <main style="max-width:1152px;margin:0 auto;padding:48px 24px;">
      <div v-if="resumeData" class="ds-card" style="padding:20px 24px;display:flex;justify-content:space-between;align-items:center;background:var(--bg-100);margin-bottom:32px;flex-wrap:wrap;gap:8px;">
        <span style="font-size:16px;font-weight:600;color:var(--text-primary);">已完成简历分析，请选择岗位</span>
        <span style="font-size:14px;color:var(--text-muted);">推荐岗位会排在首位</span>
      </div>

      <div v-if="loadingRoles" style="padding:40px;text-align:center;color:var(--text-muted);">正在加载岗位…</div>
      <div v-else-if="roleError" class="ds-card" style="padding:24px;text-align:center;border-color:rgba(220,38,38,.25);">
        <p style="color:var(--error);margin-bottom:16px;">{{ roleError }}</p>
        <button class="ds-btn ds-btn-outline" @click="loadRoles">重新加载</button>
      </div>
      <div v-else style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:20px;">
        <article v-for="role in roles" :key="role.key" class="ds-card" :style="role.key===suggestedRole?{borderLeft:'4px solid var(--brand-900)',padding:'24px',cursor:'pointer'}:{padding:'24px',cursor:'pointer'}" @click="selectRole(role)">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">
            <span v-if="role.key===suggestedRole" class="ds-pill" style="background:var(--brand-900);color:var(--brand-50);font-weight:600;font-size:11px;">推荐</span>
            <h3 style="font-size:16px;font-weight:600;color:var(--text-primary);">{{ role.title }}</h3>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px;">
            <span v-for="tag in role.tags.slice(0,4)" :key="tag" class="ds-pill">{{ tag }}</span>
          </div>
          <button class="ds-btn ds-btn-primary" style="font-size:13px;padding:8px 18px;">开始面试</button>
        </article>
      </div>
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getRoles } from '../api'
import TopNav from '../components/TopNav.vue'

const router = useRouter()
const roles = ref([])
const resumeData = ref(null)
const suggestedRole = ref('')
const loadingRoles = ref(false)
const roleError = ref('')

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
    roles.value = [...result.roles]
    suggestedRole.value = resumeData.value?.suggested_role || ''
    const suggestedIndex = roles.value.findIndex((role) => role.key === suggestedRole.value)
    if (suggestedIndex > 0) {
      const [suggested] = roles.value.splice(suggestedIndex, 1)
      roles.value.unshift(suggested)
    }
  } finally {
    loadingRoles.value = false
  }
}

function selectRole(role) {
  const config = {
    key: role.key,
    title: role.title,
    resumeContext: resumeData.value?.resume_context || '',
    resumeSkills: resumeData.value?.skills || [],
    questionCount: 5,
  }
  sessionStorage.setItem('selectedRole', JSON.stringify(config))
  // 记住最近一次面试配置 (含简历上下文), 刷新面试页可直接续上
  localStorage.setItem('interviewConfig', JSON.stringify(config))
  router.push('/interview')
}

onMounted(() => {
  const stored = sessionStorage.getItem('resumeData')
  if (stored) {
    try { resumeData.value = JSON.parse(stored) } catch (_) { resumeData.value = null }
  }
  loadRoles()
})
</script>
