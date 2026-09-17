<template>
  <div class="ir-page">
    <div class="ir-head">
      <div class="ir-head-left">
        <h1 class="ir-title">面试记录</h1>
        <p class="ir-sub">你所有面试的逐题答题记录，可随时回看复盘</p>
      </div>
      <button class="ds-btn ds-btn-ghost ir-refresh-btn" @click="loadRecords" :disabled="loading">
        <DSIcon name="refresh" :size="14" />{{ loading ? '刷新中' : '刷新' }}
      </button>
    </div>

    <div class="ir-body">
      <!-- 左: 记录列表 -->
      <div class="ir-list ds-card">
        <div v-if="loading" class="ir-empty">加载中…</div>
        <div v-else-if="!records.length" class="ir-empty">
          <div class="ir-empty-icon"><DSIcon name="file-text" :size="28" /></div>
          <div>暂无面试记录</div>
          <div class="ir-empty-hint">完成一场面试后，答题过程会自动保存到这里</div>
        </div>
        <button v-else
          v-for="r in records" :key="r.filename"
          class="ir-item" :class="{ active: selected === r.filename }"
          @click="selectRecord(r.filename)">
          <div class="ir-item-main">
            <div class="ir-item-title">{{ r.role_title || '未知岗位' }}</div>
            <div class="ir-item-meta">
              <span class="ir-badge">{{ r.difficulty_label || '-' }}</span>
              <span class="ir-badge">{{ r.total_count || '-' }} 题</span>
              <span v-if="r.size" class="ir-badge">{{ (r.size / 1024).toFixed(1) }} KB</span>
            </div>
          </div>
          <div v-if="r.timestamp" class="ir-item-ts">{{ formatTs(r.timestamp) }}</div>
          <span class="ir-item-del" role="button" tabindex="0" :title="'删除'"
                @click.stop="deleteRecord(r.filename)"
                @mousedown.stop
                @keydown.enter.stop="deleteRecord(r.filename)">
            <DSIcon name="trash-2" :size="14" />
          </span>
        </button>
      </div>

      <!-- 右: 记录内容 -->
      <div class="ir-content ds-card">
        <div v-if="!selected" class="ir-empty">
          <div class="ir-empty-icon"><DSIcon name="mouse-pointer-click" :size="28" /></div>
          <div>点击左侧记录查看内容</div>
        </div>
        <template v-else>
          <div class="ir-content-head">
            <div class="ir-content-filename">{{ selected }}</div>
            <button class="ds-btn ds-btn-ghost" style="padding:6px 12px;font-size:12px;"
                    :disabled="!content" @click="copyContent">
              <DSIcon name="copy" :size="13" />复制
            </button>
          </div>
          <div class="ir-content-body">
            <div v-if="contentLoading" class="ir-empty">加载中…</div>
            <pre v-else-if="content" class="ir-md">{{ content }}</pre>
            <div v-else class="ir-empty">加载失败</div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listInterviewRecords, getInterviewRecord, deleteInterviewRecord } from '../api'
import DSIcon from '../components/DSIcon.vue'

const records = ref([])
const loading = ref(false)
const selected = ref('')
const content = ref('')
const contentLoading = ref(false)

async function loadRecords() {
  loading.value = true
  try {
    const r = await listInterviewRecords()
    if (r.success) {
      records.value = r.records || []
      // 选中的记录如果还在列表里则保持，否则选最新一条
      if (!selected.value || !records.value.find(x => x.filename === selected.value)) {
        selected.value = records.value[0]?.filename || ''
      }
       // 选中项变化时必须主动加载内容, 否则右侧只有文件名却显示"加载失败"
      if (selected.value) await selectRecord(selected.value)
    }
  } finally {
    loading.value = false
  }
}

async function selectRecord(fn) {
  selected.value = fn
  content.value = ''
  contentLoading.value = true
  try {
    const r = await getInterviewRecord(fn)
    content.value = r.success ? r.content : `加载失败: ${r.message}`
  } finally {
    contentLoading.value = false
  }
}

function copyContent() {
  if (!content.value) return
  navigator.clipboard?.writeText(content.value).then(() => {
    alert('已复制到剪贴板')
  }).catch(() => {
    const ta = document.createElement('textarea')
    ta.value = content.value; document.body.appendChild(ta); ta.select()
    try { document.execCommand('copy'); alert('已复制到剪贴板') } catch (_) {}
    document.body.removeChild(ta)
  })
}

function formatTs(ts) {
  // ts 形如 20260827_095102
  if (!ts || ts.length < 15) return ts
  const d = `${ts.slice(0,4)}-${ts.slice(4,6)}-${ts.slice(6,8)}`
  const t = `${ts.slice(9,11)}:${ts.slice(11,13)}:${ts.slice(13,15)}`
  return `${d} ${t}`
}

async function deleteRecord(fn) {
  if (!confirm(`确定删除这条记录吗？\n${fn}`)) return
  const r = await deleteInterviewRecord(fn)
  if (r.success) {
    if (selected.value === fn) selected.value = ''
    await loadRecords()
  } else {
    alert(`删除失败: ${r.message}`)
  }
}

onMounted(() => loadRecords())
</script>

<style scoped>
.ir-page {
  padding: 32px 28px;
  min-height: calc(100vh - 0px);
  box-sizing: border-box;
}

.ir-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  gap: 16px;
}
.ir-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 4px;
}
.ir-sub {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0;
}
.ir-refresh-btn {
  flex-shrink: 0;
}

.ir-body {
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 20px;
  min-height: 500px;
}

.ir-list {
  padding: 8px;
  max-height: calc(100vh - 180px);
  overflow-y: auto;
  align-self: start;
}

.ir-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  text-align: left;
  background: none;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.18s ease;
  margin-bottom: 4px;
}
.ir-item:hover {
  background: var(--bg-100);
  border-color: var(--border-default);
}
.ir-item.active {
  background: var(--brand-50);
  border-color: var(--brand-300);
}

.ir-item-main {
  flex: 1;
  min-width: 0;
}
.ir-item-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ir-item-meta {
  display: flex;
  gap: 4px;
  align-items: center;
  flex-wrap: wrap;
}
.ir-badge {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-200);
  border-radius: 4px;
  padding: 1px 6px;
  line-height: 1.6;
}
.ir-item-ts {
  font-size: 11px;
  color: var(--text-faint);
  font-family: var(--font-mono);
  white-space: nowrap;
  flex-shrink: 0;
}
.ir-item-del {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  color: var(--text-faint);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.18s ease, color 0.18s ease, background 0.18s ease;
}
.ir-item:hover .ir-item-del { opacity: 1; }
.ir-item-del:hover { color: var(--error); background: var(--error-bg); }
.ir-content {
  padding: 0;
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 180px);
  overflow: hidden;
}
.ir-content-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-default);
  gap: 12px;
  flex-shrink: 0;
}
.ir-content-filename {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ir-content-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}
.ir-md {
  margin: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
  line-height: 1.75;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

.ir-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 48px 24px;
  color: var(--text-muted);
  font-size: 14px;
  text-align: center;
}
.ir-empty-icon {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--bg-100);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-faint);
  margin-bottom: 4px;
}
.ir-empty-hint {
  font-size: 12px;
  color: var(--text-faint);
}

@media (max-width: 768px) {
  .ir-body {
    grid-template-columns: 1fr;
  }
  .ir-content {
    max-height: none;
  }
}
</style>
