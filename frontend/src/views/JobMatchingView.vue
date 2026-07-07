<template>
  <div>
    <TopNav back-text="返回上传" />
    <main style="max-width:1152px;margin:0 auto;padding:48px 24px;">
      <div v-if="resumeData" class="ds-card" style="padding:20px 24px;display:flex;justify-content:space-between;align-items:center;background:var(--bg-100);margin-bottom:32px;flex-wrap:wrap;gap:8px;">
        <span style="font-size:16px;font-weight:600;color:var(--text-primary);">已为你匹配到岗位</span>
        <span style="font-size:14px;color:var(--text-muted);">基于你的简历分析</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:20px;">
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
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getRoles } from '../api'
import TopNav from '../components/TopNav.vue'
const router = useRouter()
const roles = ref([])
const resumeData = ref(null)
const suggestedRole = ref(null)
onMounted(async () => {
  const s = sessionStorage.getItem('resumeData'); if(s) resumeData.value = JSON.parse(s)
  const r = await getRoles()
  if(r.success) { roles.value = r.roles; if(resumeData.value?.suggested_role) { suggestedRole.value=resumeData.value.suggested_role; const i=roles.value.findIndex(x=>x.key===suggestedRole.value); if(i>0){const[item]=roles.value.splice(i,1);roles.value.unshift(item)} } }
})
function selectRole(role) { sessionStorage.setItem('selectedRole',JSON.stringify({key:role.key,title:role.title,resumeContext:resumeData.value?.resume_context||'',resumeSkills:resumeData.value?.skills||[]})); router.push('/interview') }
</script>
