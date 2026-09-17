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
          <div class="sum-list-title good"><DSIcon name="thumbs-up" :size="13" />优势项</div>
          <div v-for="s in radar.strengths" :key="s" style="font-size:13px;color:var(--text-secondary);margin-bottom:4px;">{{ s }}</div>
        </div>
        <div v-if="radar.weaknesses.length" style="flex:1;min-width:200px;">
          <div class="sum-list-title bad"><DSIcon name="triangle-alert" :size="13" />待加强</div>
          <div v-for="w in radar.weaknesses" :key="w" style="font-size:13px;color:var(--text-secondary);margin-bottom:4px;">{{ w }}</div>
        </div>
      </div>

      <!-- 学习建议 (新增) -->
      <div v-if="radar && radar.learning_suggestions && radar.learning_suggestions.length" class="ds-card" style="padding:20px;margin-bottom:24px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
          <div class="sum-section-title"><DSIcon name="book-open" :size="15" />学习建议</div>
          <button
            class="ds-btn"
            :class="kbImported ? 'ds-btn-ghost' : 'ds-btn-primary'"
            style="padding:5px 14px;font-size:13px;display:inline-flex;align-items:center;gap:5px;"
            :disabled="kbImporting || kbImported"
            @click="importToKnowledge"
          ><DSIcon :name="kbImported ? 'check' : 'download'" :size="13" />{{ kbImported ? `已入库 ${kbImportedCount} 条` : (kbImporting ? '入库中…' : '存入知识库') }}</button>
        </div>

        <!-- 覆盖检测: 已入库后展示每条薄弱点的知识库覆盖情况 -->
        <div v-if="kbCoverage" style="margin-bottom:16px;padding:12px;border-radius:8px;background:#fafafa;border:1px solid var(--border-default);">
          <div class="sum-sub-title"><DSIcon name="target" :size="13" />知识库覆盖情况</div>
          <div v-for="c in kbCoverage" :key="c.topic" style="font-size:12.5px;margin-bottom:6px;display:flex;align-items:flex-start;gap:6px;">
            <DSIcon v-if="c.matched.length" name="circle-check" :size="14" class="sum-ic good" />
            <DSIcon v-else name="triangle-alert" :size="14" class="sum-ic warn" />
            <span style="color:var(--text-secondary);">
              {{ c.topic }}：
              <template v-if="c.matched.length">
                已有 {{ c.matched.length }} 条相关
                <a v-for="m in c.matched" :key="m.note_id" href="javascript:void(0)"
                   style="color:var(--brand-600,#2563eb);margin-right:6px;"
                   @click="$router.push(`/knowledge/note/${m.note_id}`)">「{{ m.title }}」</a>
              </template>
              <template v-else>
                知识库中无相关内容，
                <router-link to="/knowledge" style="color:#b45309;font-weight:600;">建议导入对应资料 →</router-link>
              </template>
            </span>
          </div>
        </div>

        <div v-for="(item, idx) in radar.learning_suggestions" :key="idx" style="margin-bottom:16px;padding:12px;background:var(--bg-secondary,#f4f4f5);border-radius:8px;border-left:3px solid var(--brand-600);">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
            <div style="font-size:14px;font-weight:600;color:var(--text-primary);">{{ item.topic }}</div>
            <div style="font-size:12px;color:var(--text-muted);">{{ item.category }} · {{ item.score }}/10</div>
          </div>
          <div style="font-size:13px;color:var(--text-secondary);line-height:1.6;">{{ item.suggestion }}</div>
        </div>
      </div>

      <!-- 好答案 vs 差答案对比 (新增) -->
      <div v-if="radar && radar.questions && radar.questions.some(q => q.good_points && q.good_points.length)" class="ds-card" style="padding:20px;margin-bottom:24px;">
        <div class="sum-section-title" style="margin:0 0 16px;"><DSIcon name="funnel" :size="15" />好答案 vs 差答案</div>
        <div v-for="(q, idx) in radar.questions.filter(q => q.good_points && q.good_points.length)" :key="idx" style="padding-bottom:20px;border-bottom:1px solid var(--border-default);margin-bottom:16px;">
          <div style="font-size:13px;font-weight:600;color:var(--text-secondary);margin-bottom:8px;">第 {{ q.round }} 题 · {{ q.question }}</div>
          <div style="display:flex;gap:16px;flex-wrap:wrap;">
            <div style="flex:1;min-width:240px;padding:12px;background:#f0fdf4;border-left:3px solid #16a34a;border-radius:8px;">
              <div class="sum-compare-title good"><DSIcon name="thumbs-up" :size="12" />高分答案特征</div>
              <div v-for="p in q.good_points" :key="p" style="font-size:12.5px;color:var(--text-secondary);line-height:1.6;margin-bottom:3px;">{{ p }}</div>
            </div>
            <div v-if="q.bad_points && q.bad_points.length" style="flex:1;min-width:240px;padding:12px;background:#fef2f2;border-left:3px solid #dc2626;border-radius:8px;">
              <div class="sum-compare-title bad"><DSIcon name="thumbs-down" :size="12" />低分踩坑特征</div>
              <div v-for="p in q.bad_points" :key="p" style="font-size:12.5px;color:var(--text-secondary);line-height:1.6;margin-bottom:3px;">{{ p }}</div>
            </div>
          </div>
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
import DSIcon from '../components/DSIcon.vue'
import { getReport, getReportRadar, kbImportFromReport } from '../api'

const route = useRoute()
const reportId = computed(() => String(route.params.reportId || ''))
const roleTitle = ref(sessionStorage.getItem('roleTitle') || '模拟面试')
const cachedReportId = sessionStorage.getItem('reportId') || ''
const rawReport = ref(cachedReportId === reportId.value ? (sessionStorage.getItem('reportData') || '') : '')
const answeredCount = ref(sessionStorage.getItem('answeredCount') || '0')
const totalCount = ref(sessionStorage.getItem('totalCount') || '0')
const elapsedTime = ref(sessionStorage.getItem('elapsedTime') || '00:00')
const radar = ref(null)

// 学习建议一键入库 (v0.7; v0.8 返回覆盖检测)
const kbImporting = ref(false)
const kbImported = ref(false)
const kbImportedCount = ref(0)
const kbCoverage = ref(null)

async function importToKnowledge() {
  if (kbImporting.value || kbImported.value || !radar.value) return
  kbImporting.value = true
  try {
    const items = radar.value.learning_suggestions.map(s => ({
      topic: s.topic,
      suggestion: s.suggestion,
    }))
    const result = await kbImportFromReport(items, reportId.value)
    if (result.success) {
      kbImportedCount.value = result.created.length
      kbImported.value = true
      kbCoverage.value = result.coverage || null
      const skipped = result.skipped.length
        ? `（${result.skipped.length} 条同名笔记已存在，跳过）` : ''
      const sparseCount = (result.coverage || []).filter(c => c.sparse).length
      const sparseTip = sparseCount ? `\n注意：${sparseCount} 个薄弱点在知识库中无相关内容，建议导入资料。` : ''
      alert(`已存入知识库 ${result.created.length} 条${skipped}${sparseTip}\n详见下方「知识库覆盖情况」。`)
    } else {
      alert(result.message || '入库失败，请重试')
    }
  } finally {
    kbImporting.value = false
  }
}

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

<style scoped>
.sum-section-title {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.sum-sub-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.sum-list-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}
.sum-list-title.good { color: var(--success, #16a34a); }
.sum-list-title.bad { color: var(--error, #dc2626); }

.sum-compare-title {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 6px;
}
.sum-compare-title.good { color: #16a34a; }
.sum-compare-title.bad { color: #dc2626; }

.sum-ic { flex-shrink: 0; margin-top: 2px; }
.sum-ic.good { color: var(--success, #16a34a); }
.sum-ic.warn { color: #b45309; }
</style>
