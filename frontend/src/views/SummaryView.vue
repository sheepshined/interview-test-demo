<template>
  <div>
    <TopNav back-text="返回首页" />
    <main style="max-width:800px;margin:0 auto;padding:48px 24px;">
      <h1 style="font-size:24px;font-weight:600;color:var(--text-primary);margin-bottom:4px;">面试总结报告</h1>
      <p style="font-size:14px;color:var(--text-muted);margin-bottom:24px;">{{ roleTitle }}</p>

      <!-- 面试基本信息 -->
      <div class="ds-card" style="padding:20px;margin-bottom:24px;display:flex;gap:32px;flex-wrap:wrap;">
        <div style="text-align:center;min-width:80px;">
          <div style="font-size:24px;font-weight:700;color:var(--brand-900);font-family:var(--font-mono);">{{ answeredCount }}</div>
          <div style="font-size:12px;color:var(--text-muted);margin-top:4px;">回答题数</div>
        </div>
        <div style="text-align:center;min-width:80px;">
          <div style="font-size:24px;font-weight:700;color:var(--brand-900);font-family:var(--font-mono);">{{ totalCount }}</div>
          <div style="font-size:12px;color:var(--text-muted);margin-top:4px;">总题数</div>
        </div>
        <div style="text-align:center;min-width:80px;">
          <div style="font-size:24px;font-weight:700;color:var(--brand-900);font-family:var(--font-mono);">{{ elapsedTime }}</div>
          <div style="font-size:12px;color:var(--text-muted);margin-top:4px;">用时</div>
        </div>
        <div style="text-align:center;min-width:80px;">
          <div style="font-size:14px;font-weight:600;color:var(--text-primary);padding-top:6px;">{{ roleTitle }}</div>
          <div style="font-size:12px;color:var(--text-muted);margin-top:4px;">面试岗位</div>
        </div>
      </div>

      <!-- 报告内容 -->
      <div class="ds-card" style="padding:24px;margin-bottom:24px;max-height:600px;overflow-y:auto;">
        <div v-if="reportLines.length" style="font-size:14px;line-height:1.9;">
          <div v-for="(line,i) in reportLines" :key="i">
            <h2 v-if="line.tag==='h2'" style="font-size:18px;font-weight:700;margin:20px 0 8px;color:var(--text-primary);">{{ line.text }}</h2>
            <h3 v-else-if="line.tag==='h3'" style="font-size:15px;font-weight:600;margin:14px 0 6px;color:var(--text-secondary);">{{ line.text }}</h3>
            <hr v-else-if="line.tag==='hr'" style="border:none;border-top:1px solid var(--border-default);margin:16px 0;" />
            <p v-else-if="line.tag==='li'" style="padding-left:16px;position:relative;color:var(--text-secondary);"><span style="position:absolute;left:4px;color:var(--brand-600);">●</span>{{ line.text }}</p>
            <p v-else-if="line.tag==='br'" style="height:8px;"></p>
            <p v-else style="color:var(--text-secondary);">{{ line.text }}</p>
          </div>
        </div>
        <div v-else style="text-align:center;color:var(--text-muted);padding:40px;">
          暂无报告数据，请返回面试页面生成报告。
        </div>
      </div>
      <div style="display:flex;gap:12px;justify-content:center;">
        <router-link to="/" class="ds-btn ds-btn-primary">再来一次面试</router-link>
        <button class="ds-btn ds-btn-outline" @click="copyReport">复制报告</button>
      </div>
    </main>
  </div>
</template>
<script setup>
import { ref, computed } from 'vue'
import TopNav from '../components/TopNav.vue'
const roleTitle = ref(sessionStorage.getItem('roleTitle')||'模拟面试')
const rawReport = ref(sessionStorage.getItem('reportData')||'')
const answeredCount = ref(sessionStorage.getItem('answeredCount')||'0')
const totalCount = ref(sessionStorage.getItem('totalCount')||'0')
const elapsedTime = ref(sessionStorage.getItem('elapsedTime')||'00:00')
const reportLines = computed(() => {
  if(!rawReport.value)return[]
  return rawReport.value.split('\n').map(l=>{
    const t=l.trim()
    if(!t)return{text:'',tag:'br'}
    if(t.startsWith('## '))return{text:t.replace('## ',''),tag:'h2'}
    if(t.startsWith('# '))return{text:t.replace('# ',''),tag:'h2'}
    if(t.startsWith('### '))return{text:t.replace('### ',''),tag:'h3'}
    if(t.startsWith('---'))return{text:'',tag:'hr'}
    if(t.startsWith('- '))return{text:t.replace('- ',''),tag:'li'}
    return{text:t,tag:'p'}
  })
})
function copyReport(){
  navigator.clipboard.writeText(rawReport.value)
  alert('报告已复制到剪贴板')
}
</script>
