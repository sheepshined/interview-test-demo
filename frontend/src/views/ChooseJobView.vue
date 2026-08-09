<template>
  <div>
    <TopNav back-text="返回首页" />
    <main style="max-width:700px;margin:0 auto;padding:48px 24px;">
      <h1 style="font-size:24px;font-weight:600;color:var(--text-primary);margin-bottom:8px;">选择面试配置</h1>
      <p style="font-size:14px;color:var(--text-muted);margin-bottom:32px;">自定义你的模拟面试参数</p>
      <div class="ds-card" style="padding:28px;">
        <div style="margin-bottom:24px;">
          <label style="display:block;font-size:14px;font-weight:600;margin-bottom:12px;color:var(--text-primary);">岗位类别</label>
          <div style="display:flex;flex-wrap:wrap;gap:8px;">
            <span v-for="role in roles" :key="role.key" class="chip" :class="{active:selectedRole===role.key}" @click="selectedRole=role.key">{{ role.title }}</span>
          </div>
        </div>
        <div style="margin-bottom:24px;">
          <label style="display:block;font-size:14px;font-weight:600;margin-bottom:12px;color:var(--text-primary);">面试类型</label>
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;">
            <div v-for="t in interviewTypes" :key="t.value" class="type-card" :class="{active:interviewType===t.value}" @click="interviewType=t.value">
              <div class="type-icon-wrap"><DSIcon :name="t.icon" :size="24" color="var(--brand-600)" /></div>
              <strong style="font-size:14px;display:block;margin-top:4px;">{{ t.label }}</strong>
              <p style="font-size:12px;margin-top:4px;color:var(--text-muted);">{{ t.desc }}</p>
            </div>
          </div>
        </div>
        <div>
          <label style="display:block;font-size:14px;font-weight:600;margin-bottom:12px;color:var(--text-primary);">面试题量</label>
          <div style="display:flex;gap:10px;">
            <button v-for="c in countOptions" :key="c.value" class="count-btn" :class="{active:questionCount===c.value}" @click="questionCount=c.value">{{ c.label }}</button>
          </div>
        </div>
      </div>
      <button class="ds-btn ds-btn-primary w-full" style="padding:14px;margin-top:24px;" @click="startInterview" :disabled="!selectedRole">开始面试 →</button>
    </main>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getRoles } from '../api'
import TopNav from '../components/TopNav.vue'
import DSIcon from '../components/DSIcon.vue'
const router = useRouter()
const roles = ref([])
const selectedRole = ref('')
const interviewType = ref('technical')
const questionCount = ref(5)
const interviewTypes = [{value:'technical',label:'技术面试',icon:'pen-line',desc:'考察专业技能和项目经验'},{value:'hr',label:'HR面试',icon:'user',desc:'考察综合素质和沟通表达'},{value:'general',label:'综合面试',icon:'star',desc:'技术 + HR 综合考察'}]
const countOptions = [{value:5,label:'5 题 (约10分钟)'},{value:10,label:'10 题 (约20分钟)'},{value:15,label:'15 题 (约30分钟)'}]
onMounted(async () => { const r=await getRoles(); if(r.success){roles.value=r.roles;if(roles.value.length)selectedRole.value=roles.value[0].key} })
function startInterview() { const role=roles.value.find(r=>r.key===selectedRole.value); sessionStorage.setItem('selectedRole',JSON.stringify({key:selectedRole.value,title:role?.title||'',resumeContext:'',resumeSkills:[],questionCount:questionCount.value})); router.push('/interview') }
</script>
<style scoped>
.chip{padding:8px 18px;border-radius:999px;font-size:13px;cursor:pointer;border:1px solid var(--border-default);background:var(--surface);color:var(--text-secondary);transition:all 0.16s;}
.chip.active{background:var(--brand-900);color:var(--brand-50);border-color:var(--brand-900);}
.type-card{border:1px solid var(--border-default);border-radius:var(--radius-md);padding:18px;text-align:center;cursor:pointer;transition:all 0.16s;}
.type-card:hover{border-color:var(--brand-400);}
.type-card.active{border-color:var(--brand-900);background:var(--bg-100);}
.type-icon-wrap{width:48px;height:48px;border-radius:12px;background:var(--bg-100);display:flex;align-items:center;justify-content:center;margin:0 auto 8px;}
.count-btn{padding:10px 18px;border:1px solid var(--border-default);border-radius:var(--radius-md);background:var(--surface);color:var(--text-secondary);font-size:13px;cursor:pointer;transition:all 0.16s;}
.count-btn.active{background:var(--brand-900);color:var(--brand-50);border-color:var(--brand-900);}
@media(max-width:640px){.type-card-parent{grid-template-columns:1fr!important;}}
</style>
