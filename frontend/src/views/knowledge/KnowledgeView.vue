<template>
  <div class="kb-page">
    <TopNav />

    <div class="kb-container">
      <div class="kb-header">
        <div>
          <h1 class="kb-title">我的笔记</h1>
          <p class="kb-subtitle">上传文件 / 收藏网址 / 手写笔记，[[双链语法]] 连接知识</p>
        </div>
        <div class="kb-header-actions">
          <button class="ds-btn ds-btn-ghost kb-action-btn" :disabled="uploading" @click="pickFiles">
            <DSIcon name="upload" :size="15" />
            {{ uploading ? `导入中 (${uploadCount} 个文件)…` : '导入文件' }}
          </button>
          <button class="ds-btn ds-btn-ghost kb-action-btn" @click="urlDialog = true">
            <DSIcon name="link" :size="15" />添加网址
          </button>
          <router-link to="/knowledge/new" class="ds-btn ds-btn-primary kb-new-btn">
            <DSIcon name="plus" :size="16" />新建笔记
          </router-link>
        </div>
        <input ref="fileInput" type="file" multiple hidden
               accept=".md,.markdown,.txt,.pptx,.docx,.pdf" @change="onFilesPicked" />
      </div>

      <!-- 上传结果明细 -->
      <div v-if="uploadResults" class="ds-card kb-upload-result">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          <span style="font-size:13px;font-weight:600;">导入结果</span>
          <button class="side-close" @click="uploadResults = null">×</button>
        </div>
        <div v-for="r in uploadResults" :key="r.file" class="kb-upload-row">
          <span class="kb-upload-status" :class="r.status">{{ statusLabel(r.status) }}</span>
          <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
            {{ r.title || r.file }}
          </span>
          <span v-if="r.pages" style="font-size:12px;color:var(--text-faint);flex-shrink:0;">{{ r.pages }}页·{{ r.extract_mode }}{{ r.llm_used ? '·AI整理' : '' }}</span>
          <span v-if="r.message" style="font-size:12px;color:var(--error);flex-shrink:0;max-width:40%;">{{ r.message }}</span>
        </div>
      </div>

      <!-- 网址收藏弹窗 -->
      <div v-if="urlDialog" class="kb-modal-mask" @click.self="urlDialog = false">
        <div class="ds-card kb-modal">
          <div style="font-size:16px;font-weight:600;margin-bottom:16px;display:flex;align-items:center;gap:8px;">
            <DSIcon name="link" :size="16" />添加网址
          </div>
          <label class="kb-label">网址 *</label>
          <input v-model="urlForm.url" class="ds-input" placeholder="https://..." />
          <label class="kb-label">标题（留空用网址）</label>
          <input v-model="urlForm.title" class="ds-input" placeholder="如: BGE 模型卡" />
          <label class="kb-label">描述 *（检索匹配的主体，请认真填写）</label>
          <textarea v-model="urlForm.description" class="ds-input" rows="3"
                    placeholder="这个网页讲了什么？为什么收藏它？" />
          <label class="kb-label">分类（可选）</label>
          <input v-model="urlForm.category" class="ds-input" list="kb-cat-list" placeholder="如: 大模型" />
          <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:18px;">
            <button class="ds-btn ds-btn-ghost" style="padding:8px 14px;" @click="urlDialog = false">取消</button>
            <button class="ds-btn ds-btn-primary" style="padding:8px 18px;"
                    :disabled="!urlForm.url.trim() || !urlForm.description.trim() || urlSaving"
                    @click="saveUrl">{{ urlSaving ? '保存中…' : '保存' }}</button>
          </div>
        </div>
      </div>

      <div class="kb-toolbar">
        <input
          v-model="search"
          class="ds-input kb-search"
          placeholder="搜索标题或内容…"
          @input="onSearchInput"
        />
        <div class="kb-chips">
          <button
            v-for="c in categories"
            :key="'c-' + c.category"
            class="kb-tag kb-cat-tag"
            :class="{ active: activeCategory === c.category }"
            @click="toggleCategory(c.category)"
          ><DSIcon name="folder" :size="12" />{{ c.category }} ({{ c.count }})</button>
        </div>
        <div v-if="visibleTags.length" class="kb-tags">
          <button
            v-for="t in visibleTags"
            :key="t"
            class="kb-tag"
            :class="{ active: activeTag === t }"
            @click="toggleTag(t)"
          >{{ t }}</button>
          <button v-if="allTags.length > 8" class="kb-tag kb-tags-toggle" @click="tagsExpanded = !tagsExpanded">
            <DSIcon :name="tagsExpanded ? 'chevrons-down-up' : 'chevrons-up-down'" :size="12" />
            {{ tagsExpanded ? '收起' : `+${allTags.length - 8}` }}
          </button>
        </div>
      </div>

      <div v-if="loading" class="kb-empty">加载中…</div>
      <div v-else-if="error" class="kb-empty" style="color: var(--error);">{{ error }}</div>
      <div v-else-if="!notes.length" class="kb-empty">
        还没有笔记。导入文件、收藏网址，或在面试报告页把薄弱点一键入库。
      </div>

      <div v-else class="kb-grid">
        <div v-for="note in notes" :key="note.id" class="kb-card ds-card" @click="openNote(note.id)">
          <div class="kb-card-head">
            <span class="kb-type-badge" :class="note.note_type" :title="typeLabel(note.note_type)">
              <DSIcon :name="typeIconOf(note.note_type)" :size="13" />
            </span>
            <span class="kb-card-title">{{ note.title }}</span>
            <span v-if="note.source === 'interview_report'" class="kb-badge">面试</span>
            <a v-if="note.note_type === 'url' && note.source_url" :href="note.source_url"
               target="_blank" rel="noopener" class="kb-open-link" title="打开网址"
               @click.stop><DSIcon name="external-link" :size="13" /></a>
          </div>
          <p class="kb-card-excerpt">{{ note.content || '（空笔记）' }}</p>
          <div class="kb-card-meta">
            <span v-if="note.category" class="kb-tag small cat">{{ note.category }}</span>
            <span v-for="t in note.tags.slice(0, 3)" :key="t" class="kb-tag small">{{ t }}</span>
            <span class="kb-card-links"><DSIcon name="link" :size="12" />{{ note.link_count }}</span>
            <span class="kb-card-date">{{ formatDate(note.updated_at) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import TopNav from '../../components/TopNav.vue'
import DSIcon from '../../components/DSIcon.vue'
import { kbListNotes, kbCategories, kbUploadFiles, kbCreateUrlNote } from '../../api'

const router = useRouter()
const notes = ref([])
const allTags = ref([])
const categories = ref([])
const activeCategory = ref('')
const activeTag = ref('')
const search = ref('')
const loading = ref(false)
const error = ref('')
const tagsExpanded = ref(false)

const visibleTags = computed(() => tagsExpanded.value ? allTags.value : allTags.value.slice(0, 8))

const fileInput = ref(null)
const uploading = ref(false)
const uploadResults = ref(null)
const uploadCount = ref(0)

const urlDialog = ref(false)
const urlSaving = ref(false)
const urlForm = ref({ url: '', title: '', description: '', category: '' })

let searchTimer = null

async function load() {
  loading.value = true
  error.value = ''
  try {
    const result = await kbListNotes(search.value, activeTag.value, activeCategory.value)
    if (!result.success) {
      error.value = result.message || '加载失败'
      return
    }
    notes.value = result.notes
    if (!search.value && !activeTag.value && !activeCategory.value) {
      const seen = new Set()
      const tags = []
      for (const n of result.notes) {
        for (const t of n.tags) {
          if (!seen.has(t)) { seen.add(t); tags.push(t) }
        }
      }
      allTags.value = tags
    }
  } finally {
    loading.value = false
  }
}

async function loadCategories() {
  const result = await kbCategories()
  if (result.success) categories.value = result.categories
}

function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(load, 300)
}

function toggleTag(t) {
  activeTag.value = activeTag.value === t ? '' : t
  load()
}

function toggleCategory(c) {
  activeCategory.value = activeCategory.value === c ? '' : c
  load()
}

function openNote(id) {
  router.push(`/knowledge/note/${id}`)
}

// ---- 文件上传 ----
function pickFiles() { fileInput.value?.click() }

async function onFilesPicked(e) {
  const files = [...(e.target.files || [])]
  e.target.value = ''   // 允许重复选同一文件
  if (!files.length || uploading.value) return
  uploading.value = true
  uploadResults.value = null
  uploadCount.value = files.length
  try {
    const result = await kbUploadFiles(files)
    if (result.success) {
      uploadResults.value = result.results
      await Promise.all([load(), loadCategories()])
    } else {
      alert(result.message || '上传失败')
    }
  } finally {
    uploading.value = false
  }
}

function statusLabel(s) {
  return { created: '成功', skipped: '跳过', failed: '失败' }[s] || s
}

// ---- 网址收藏 ----
async function saveUrl() {
  if (urlSaving.value) return
  urlSaving.value = true
  try {
    const result = await kbCreateUrlNote(
      urlForm.value.url.trim(), urlForm.value.title.trim(),
      urlForm.value.description.trim(), urlForm.value.category.trim(),
    )
    if (!result.success) {
      alert(result.message || '保存失败')
      return
    }
    urlDialog.value = false
    urlForm.value = { url: '', title: '', description: '', category: '' }
    await Promise.all([load(), loadCategories()])
  } finally {
    urlSaving.value = false
  }
}

function typeIconOf(t) { return { note: 'pen-line', file: 'file', url: 'link' }[t] || 'pen-line' }
function typeLabel(t) { return { note: '手写笔记', file: '文件导入', url: '网址收藏' }[t] || t }

function formatDate(iso) { return iso ? iso.slice(0, 10) : '' }

onMounted(() => { load(); loadCategories() })
</script>

<style scoped>
.kb-page { min-height: 100vh; }

.kb-container {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 28px 24px 60px;
}

.kb-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.kb-header-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }

.kb-action-btn { padding: 8px 14px; font-size: 13px; color: var(--text-secondary); }
.kb-new-btn { padding: 8px 16px; font-size: 14px; text-decoration: none; }

.kb-title { font-size: 22px; font-weight: 700; color: var(--text-primary); margin: 0 0 4px; }
.kb-subtitle { font-size: 13px; color: var(--text-muted); margin: 0; }

.kb-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.kb-search { max-width: 280px; flex: 1; min-width: 180px; }

.kb-chips, .kb-tags { display: flex; gap: 6px; flex-wrap: wrap; }

.kb-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid var(--border-default);
  background: var(--surface);
  color: var(--text-secondary);
  border-radius: 999px;
  font-size: 12px;
  padding: 3px 10px;
  cursor: pointer;
  transition: border-color var(--dur-fast) ease, background var(--dur-fast) ease, color var(--dur-fast) ease;
}

.kb-tag:hover { border-color: var(--border-strong); }
.kb-tag.active { background: var(--brand-800); border-color: var(--brand-800); color: #fff; }
.kb-tag.small { cursor: default; }
.kb-tag.cat { cursor: default; background: var(--brand-50); color: var(--brand-700); border-color: var(--brand-200); }

.kb-cat-tag { background: var(--brand-50); color: var(--brand-700); border-color: var(--brand-200); }
.kb-cat-tag:hover { border-color: var(--brand-400); }
.kb-cat-tag.active { background: var(--brand-700); border-color: var(--brand-700); color: #fff; }

.kb-tags-toggle { color: var(--text-muted); border-style: dashed; }

.kb-empty { text-align: center; color: var(--text-muted); padding: 60px 0; font-size: 14px; }

.kb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
}

.kb-card {
  padding: 16px;
  cursor: pointer;
  transition: box-shadow 0.15s ease, transform 0.15s ease;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.kb-card:hover { box-shadow: var(--shadow-sm); transform: translateY(-2px); }

.kb-card-head { display: flex; align-items: center; gap: 8px; }

.kb-type-badge {
  width: 22px; height: 22px;
  border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px;
  flex-shrink: 0;
}

.kb-type-badge.note { background: #dbeafe; color: #1d4ed8; }
.kb-type-badge.file { background: #dcfce7; color: #15803d; }
.kb-type-badge.url { background: #ffedd5; color: #c2410c; }

.kb-card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-open-link {
  flex-shrink: 0;
  font-size: 13px;
  color: var(--text-muted);
  text-decoration: none;
  padding: 0 4px;
}

.kb-open-link:hover { color: #c2410c; }

.kb-badge {
  flex-shrink: 0;
  font-size: 11px;
  background: var(--error-bg);
  color: var(--error);
  padding: 1px 8px;
  border-radius: 999px;
}

.kb-card-excerpt {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 40px;
}

.kb-card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: auto;
}

.kb-card-links { font-size: 12px; color: var(--text-faint); }
.kb-card-date { font-size: 12px; color: var(--text-faint); margin-left: auto; }

/* 上传结果 */
.kb-upload-result { padding: 14px 16px; margin-bottom: 18px; }

.kb-upload-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 0;
  font-size: 13px;
  border-top: 1px solid var(--border-default);
}

.kb-upload-row:first-of-type { border-top: none; }

.kb-upload-status { flex-shrink: 0; font-size: 12px; font-weight: 600; }
.kb-upload-status.created { color: var(--success); }
.kb-upload-status.skipped { color: #b45309; }
.kb-upload-status.failed { color: var(--error); }

.side-close {
  border: none; background: transparent; color: var(--text-muted);
  font-size: 16px; cursor: pointer; padding: 0 4px;
}

/* 弹窗 */
.kb-modal-mask {
  position: fixed; inset: 0;
  background: rgba(0,0,0,.4);
  display: flex; align-items: center; justify-content: center;
  z-index: 100;
}

.kb-modal { width: 440px; max-width: 92vw; padding: 24px; }

.kb-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 12px 0 4px;
}
</style>
