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
          <div style="font-size:24px;font-weight:700;color:var(--brand-900);font-family:var(--font-mono);">{{ radar ? radar.total_questions : totalCount }}</div>
          <div style="font-size:12px;color:var(--text-muted);margin-top:4px;">总题数</div>
        </div>
        <div style="text-align:center;min-width:80px;">
          <div style="font-size:24px;font-weight:700;color:var(--brand-900);font-family:var(--font-mono);">{{ radar ? radar.avg_score : '-' }}</div>
          <div style="font-size:12px;color:var(--text-muted);margin-top:4px;">平均分</div>
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

      <!-- 雷达图 (阶段2 新增) -->
      <div v-if="radar" class="ds-card" style="padding:16px;margin-bottom:24px;">
        <RadarChart :radar="radar" />
      </div>

      <!-- 分类得分 (阶段2 新增) -->
      <div v-if="radar && radar.categories && radar.categories.length" class="ds-card" style="padding:20px;margin-bottom:24px;">
        <h3 style="font-size:15px;font-weight:600;margin:0 0 12px;color:var(--text-primary);">分类得分</h3>
        <div v-for="cat in radar.categories" :key="cat.category" style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
          <span style="font-size:13px;color:var(--text-secondary);min-width:120px;">{{ cat.category }}</span>
          <div style="flex:1;height:8px;background:var(--bg-secondary,#f4f4f5);border-radius:4px;overflow:hidden;">
            <div :style="{width:(cat.avg_score*10)+'%',height:'100%',background:'var(--brand-600)',borderRadius:'4px'}"></div>
          </div>
          <span style="font-size:13px;font-weight:600;color:var(--brand-900);font-family:var(--font-mono);min-width:60px;">{{ cat.avg_score }}/10</span>
          <span style="font-size:12px;color:var(--text-muted);min-width:36px;">{{ cat.count }}题</span>
        </div>
      </div>

      <!-- 强弱项 (阶段2 新增) -->
      <div v-if="radar && (radar.strengths.length || radar.weaknesses.length)" class="ds-card" style="padding:20px;margin-bottom:24px;display:flex;gap:24px;flex-wrap:wrap;">
        <div v-if="radar.strengths.length" style="flex:1;min-width:200px;">
          <div style="font-size:13px;font-weight:600;color:var(--success,#16a34a);margin-bottom:8px;">✓ 优势项</div>
          <div v-for="s in radar.strengths" :key="s" style="font-size:13px;color:var(--text-secondary);margin-bottom:4px;">{{ s }}</div>
        </div>
        <div v-if="radar.weaknesses.length" style="flex:1;min-width:200px;">
          <div style="font-size:13px;font-weight:600;color:var(--error,#dc2626);margin-bottom:8px;">△ 待加强</div>
          <div v-for="w in radar.weaknesses" :key="w" style="font-size:13px;color:var(--text-secondary);margin-bottom:4px;">{{ w }}</div>
        </div>
      </div>

      <!-- 学习建议 (新增) -->
      <div v-if="radar && radar.learning_suggestions && radar.learning_suggestions.length" class="ds-card" style="padding:20px;margin-bottom:24px;">
        <div style="font-size:15px;font-weight:600;margin:0 0 16px;color:var(--text-primary);">📚 学习建议</div>
        <div v-for="(item, idx) in radar.learning_suggestions" :key="idx" style="margin-bottom:16px;padding:12px;background:var(--bg-secondary,#f4f4f5);border-radius:8px;border-left:3px solid var(--brand-600);">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
            <div style="font-size:14px;font-weight:600;color:var(--text-primary);">{{ item.topic }}</div>
            <div style="font-size:12px;color:var(--text-muted);">{{ item.category }} · {{ item.score }}/10</div>
          </div>
          <div style="font-size:13px;color:var(--text-secondary);line-height:1.6;">{{ item.suggestion }}</div>
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
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import TopNav from '../components/TopNav.vue'
import RadarChart from '../components/RadarChart.vue'
import { getReport, getReportRadar } from '../api'

const route = useRoute()
const reportId = computed(() => String(route.params.reportId || ''))
const roleTitle = ref(sessionStorage.getItem('roleTitle') || '模拟面试')
const cachedReportId = sessionStorage.getItem('reportId') || ''
const rawReport = ref(cachedReportId === reportId.value ? (sessionStorage.getItem('reportData') || '') : '')
const answeredCount = ref(sessionStorage.getItem('answeredCount') || '0')
const totalCount = ref(sessionStorage.getItem('totalCount') || '0')
const elapsedTime = ref(sessionStorage.getItem('elapsedTime') || '00:00')
const radar = ref(null)

onMounted(async () => {
  if (!reportId.value) return
  try {
    const [reportResult, radarResult] = await Promise.all([
      getReport(reportId.value),
      getReportRadar(reportId.value),
    ])
    if (reportResult.success) {
      rawReport.value = reportResult.content
      sessionStorage.setItem('reportData', reportResult.content)
      sessionStorage.setItem('reportId', reportId.value)
    }
    if (radarResult.success && radarResult.radar) {
      radar.value = radarResult.radar
      if (radarResult.radar.role_title) roleTitle.value = radarResult.radar.role_title
      answeredCount.value = String(radarResult.radar.total_questions ?? answeredCount.value)
      totalCount.value = String(radarResult.radar.total_questions ?? totalCount.value)
    }
  } catch (e) {
    console.warn(`加载报告 ${reportId.value} 失败`, e)
  }
})

const reportLines = computed(() => {
  if (!rawReport.value) return []
  return rawReport.value.split('\n').map(l => {
    const t = l.trim()
    if (!t) return { text: '', tag: 'br' }
    if (t.startsWith('## ')) return { text: t.replace('## ', ''), tag: 'h2' }
    if (t.startsWith('# ')) return { text: t.replace('# ', ''), tag: 'h2' }
    if (t.startsWith('### ')) return { text: t.replace('### ', ''), tag: 'h3' }
    if (t.startsWith('---')) return { text: '', tag: 'hr' }
    if (t.startsWith('- ')) return { text: t.replace('- ', ''), tag: 'li' }
    return { text: t, tag: 'p' }
  })
})

function copyReport() {
  navigator.clipboard.writeText(rawReport.value)
  alert('报告已复制到剪贴板')
}
</script>
