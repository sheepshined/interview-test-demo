<template>
  <div class="kb-page">
    <TopNav :back-text="'返回笔记列表'" />

    <div class="kb-container">
      <div v-if="loading" class="editor-status">加载中…</div>
      <div v-else-if="error" class="editor-status" style="color: var(--error);">{{ error }}</div>

      <template v-else>
        <!-- 标题 + 操作 -->
        <div class="editor-head">
          <div class="editor-title-row">
            <span class="kb-type-badge" :class="note?.note_type || 'note'">
              <DSIcon :name="typeIcon" :size="13" />
            </span>
            <input v-model="title" class="editor-title-input" placeholder="笔记标题" />
            <a v-if="note?.note_type === 'url' && note.source_url" :href="note.source_url"
               target="_blank" rel="noopener" class="url-open-btn" title="打开来源网址">
              <DSIcon name="external-link" :size="12" />打开来源
            </a>
          </div>
          <div class="editor-actions">
            <button v-if="!isNew" class="ds-btn ds-btn-ghost editor-action-btn"
                    :disabled="aiBusy" @click="aiTidy">
              <DSIcon name="sparkles" :size="14" />{{ aiBusy ? 'AI 处理中…' : 'AI 整理' }}
            </button>
            <button class="ds-btn ds-btn-primary editor-save-btn"
                    :disabled="saving || !title.trim()" @click="save">
              {{ saving ? '保存中…' : (isNew ? '创建' : '保存') }}
            </button>
            <button v-if="!isNew" class="ds-btn ds-btn-ghost editor-del-btn" @click="remove">
              <DSIcon name="trash-2" :size="14" />删除
            </button>
          </div>
        </div>

        <div class="editor-meta">
          <input v-model="category" class="ds-input editor-cat" list="kb-cat-list"
                 placeholder="分类 (可自由输入)" />
          <button v-if="!isNew" class="ds-btn ds-btn-ghost editor-ai-cat-btn"
                  :disabled="aiBusy" @click="aiCategory" title="AI 建议分类 (不覆盖手动输入)">
            <DSIcon name="bot" :size="13" />AI 分类
          </button>
          <input v-model="tagsInput" class="ds-input editor-tags" placeholder="标签（逗号分隔）" />
          <span v-if="note" class="editor-date">更新于 {{ fmtDate(note.updated_at) }}</span>
        </div>
        <datalist id="kb-cat-list">
          <option v-for="c in categories" :key="c.category" :value="c.category" />
        </datalist>

        <div class="editor-body">
          <div class="editor-main ds-card">
            <div v-if="insertTip" class="wiki-insert-tip">
              <DSIcon name="link" :size="13" />{{ insertTip }}
            </div>
            <div class="vditor-wrap">
              <div ref="vditorEl" class="vditor-host" />
            </div>
          </div>

          <aside class="editor-side">
            <!-- 语义检索面板 -->
            <div class="side-panel ds-card">
              <div class="side-panel-title"><DSIcon name="search" :size="13" />语义检索</div>
              <div style="display:flex;gap:6px;margin-bottom:8px;">
                <input v-model="searchQuery" class="ds-input" style="font-size:12px;padding:5px 8px;"
                       placeholder="检索知识库…" @keyup.enter="doSearch" />
                <button class="ds-btn ds-btn-ghost" style="padding:4px 10px;font-size:12px;flex-shrink:0;"
                        :disabled="searching" @click="doSearch">{{ searching ? '…' : '搜' }}</button>
              </div>
              <div v-if="searchSparse && searched" class="sparse-tip">
                <DSIcon name="triangle-alert" :size="13" class="sparse-tip-ic" />
                <span>知识库中未找到相关内容，建议导入对应资料
                <router-link to="/knowledge" style="color:#92400e;font-weight:600;">去导入 →</router-link></span>
              </div>
              <div v-if="!searchResults.length && searched && !searching" class="side-panel-empty">无匹配结果</div>
              <div v-for="r in searchResults" :key="r.note_id" class="search-hit">
                <div class="search-hit-head">
                  <span class="kb-type-badge small" :class="r.note_type"><DSIcon :name="typeIconOf(r.note_type)" :size="11" /></span>
                  <span class="search-hit-title">{{ r.title }}</span>
                  <span class="search-hit-score">{{ (r.score * 100).toFixed(0) }}%</span>
                </div>
                <p v-if="r.excerpt" class="search-hit-excerpt">{{ r.excerpt }}</p>
                <div class="search-hit-actions">
                  <a v-if="r.note_type === 'url' && r.source_url" :href="r.source_url"
                     target="_blank" rel="noopener" class="mini-link">打开链接 ↗</a>
                  <a href="javascript:void(0)" class="mini-link" @click="goNote(r.note_id)">查看</a>
                  <a href="javascript:void(0)" class="mini-link primary"
                     @click="insertLink(r.title)">插入 [[链接]]</a>
                </div>
              </div>
            </div>

            <div class="side-panel ds-card">
              <div class="side-panel-title">链接到 ({{ links.length }})</div>
              <div class="side-panel-hint">编辑区 Ctrl+点击 [[链接]] 可跳转；保存后建立双向链接</div>
              <div v-if="!links.length" class="side-panel-empty">内容中没有 [[链接]]</div>
              <a v-for="l in links" :key="l" href="javascript:void(0)" class="side-link-item"
                 :class="{ virtual: !existingTitles.has(l) }" @click="openLink(l)">
                {{ l }}
                <span v-if="!existingTitles.has(l)" class="virtual-mark">未创建</span>
              </a>
            </div>

            <div v-if="note?.file_path" class="side-panel ds-card">
              <div class="side-panel-title">原始文件</div>
              <a :href="kbFileUrl(note.file_path)" target="_blank"
                 class="side-link-item original-file-link" title="打开原始文件">
                <span class="file-icon"><DSIcon name="paperclip" :size="13" /></span>
                <span class="file-name">{{ note.file_name }}</span>
                <span class="file-open">打开 <DSIcon name="external-link" :size="11" /></span>
              </a>
            </div>

            <div class="side-panel ds-card">
              <div class="side-panel-title">反向链接 ({{ backlinks.length }})</div>
              <div v-if="!backlinks.length" class="side-panel-empty">还没有笔记链接到这里</div>
              <a v-for="b in backlinks" :key="b.id" href="javascript:void(0)"
                 class="side-link-item" @click="router.push(`/knowledge/note/${b.id}`)">{{ b.title }}</a>
            </div>
          </aside>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Vditor from 'vditor'
import 'vditor/dist/index.css'
import TopNav from '../../components/TopNav.vue'
import DSIcon from '../../components/DSIcon.vue'
import {
  kbGetNote, kbCreateNote, kbUpdateNote, kbDeleteNote, kbListNotes,
  kbCategories, kbSearch, kbTidy, kbAutoCategory, kbFileUrl,
} from '../../api'

const route = useRoute()
const router = useRouter()

// computed 而非常量: 新建保存后 router.replace 到 /note/:id, 组件被复用不会重挂载
const noteId = computed(() => route.params.id ? Number(route.params.id) : null)
const isNew = computed(() => !noteId.value)

const note = ref(null)
const title = ref('')
const category = ref('')
const tagsInput = ref('')
const backlinks = ref([])
const categories = ref([])
const existingTitles = ref(new Set())
const loading = ref(!isNew.value)
const error = ref('')
const saving = ref(false)
const aiBusy = ref(false)

// 语义检索
const searchQuery = ref('')
const searchResults = ref([])
const searchSparse = ref(false)
const searched = ref(false)
const searching = ref(false)

const vditorEl = ref(null)
let vditor = null

// 标题 → 笔记 id 映射 ([[链接]] 跳转用)
const titleIdMap = ref(new Map())

// 插入链接提示 (3 秒自动消失)
const insertTip = ref('')
let tipTimer = null
function showTip(msg) {
  insertTip.value = msg
  clearTimeout(tipTimer)
  tipTimer = setTimeout(() => { insertTip.value = '' }, 3500)
}

const typeIcon = computed(() => ({ note: 'pen-line', file: 'file', url: 'link' }[note.value?.note_type] || 'pen-line'))
function typeIconOf(t) { return { note: 'pen-line', file: 'file', url: 'link' }[t] || 'pen-line' }

const links = computed(() => {
  const text = vditor ? vditor.getValue() : ''
  const out = []
  for (const m of text.matchAll(/\[\[([^\[\]\n]{1,120})\]\]/g)) {
    const t = m[1].trim()
    if (t && !out.includes(t)) out.push(t)
  }
  return out
})

// silent=true: 只刷新数据不动 loading —— 避免模板 v-if 卸载 vditor 的 DOM (保存后界面消失的根因)
async function load(silent = false) {
  if (isNew.value) { loading.value = false; return }
  if (!silent) loading.value = true
  try {
    const result = await kbGetNote(noteId.value)
    if (!result.success) {
      error.value = result.message || '笔记不存在'
      return
    }
    note.value = result.note
    title.value = result.note.title
    category.value = result.note.category || ''
    tagsInput.value = result.note.tags.join(', ')
    backlinks.value = result.backlinks
    if (!silent) searchQuery.value = result.note.title   // 默认检索当前标题 (静默刷新不覆盖用户输入)
  } finally {
    if (!silent) loading.value = false
  }
}

async function loadRefData() {
  const [list, cats] = await Promise.all([kbListNotes(), kbCategories()])
  if (list.success) {
    existingTitles.value = new Set(list.notes.map(n => n.title))
    titleIdMap.value = new Map(list.notes.map(n => [n.title, n.id]))
  }
  if (cats.success) categories.value = cats.categories
}

function initVditor() {
  vditor = new Vditor(vditorEl.value, {
    height: '100%',
    minHeight: 480,
    mode: 'ir',
    lang: 'zh_CN',
    placeholder: '用 Markdown 记录知识，输入 [[标题]] 链接其他笔记，Ctrl+点击可跳转…',
    value: note.value ? note.value.content : '',
    toolbarConfig: { pin: true },
    toolbar: [
      'headings', 'bold', 'italic', 'strike', '|',
      'list', 'ordered-list', 'check', 'quote', '|',
      'link', 'table', 'code', 'inline-code', '|',
      'undo', 'redo', '|', 'preview', 'edit-mode', 'fullscreen',
    ],
    cache: { enable: false },
    counter: { enable: true },
    preview: { markdown: { autoSpace: true } },
  })
}

async function save() {
  if (saving.value) return
  const t = title.value.trim()
  if (!t) return
  saving.value = true
  try {
    const content = vditor ? vditor.getValue() : ''
    const tags = tagsInput.value.split(/[,，]/).map(s => s.trim()).filter(Boolean)
    const result = isNew.value
      ? await kbCreateNote(t, content, tags, category.value.trim())
      : await kbUpdateNote(noteId.value, t, content, tags, category.value.trim())
    if (!result.success) {
      alert(result.message || '保存失败')
      return
    }
    if (isNew.value) {
      // router.replace 组件被复用 (不会重跑 onMounted), noteId 是 computed 会自动切换为编辑态
      router.replace(`/knowledge/note/${result.id}`)
      await loadRefData()   // 刷新标题→id 映射 (插入的 [[链接]] 要能跳转)
    } else {
      // 静默刷新: 不切 loading, 否则 v-if 会卸载 vditor 的 DOM 导致编辑器空白
      await load(true)
      await loadRefData()   // 标题可能改过, 刷新映射与反链
      await doSearch()      // 内容变了, 刷新检索
    }
  } finally {
    saving.value = false
  }
}

// ---- 语义检索 ----
async function doSearch() {
  const q = searchQuery.value.trim()
  if (!q || searching.value) return
  searching.value = true
  try {
    const result = await kbSearch(q, 2)
    if (result.success) {
      searchResults.value = result.results
      searchSparse.value = result.sparse
      searched.value = true
    }
  } finally {
    searching.value = false
  }
}

function insertLink(targetTitle) {
  if (!vditor) return
  vditor.focus()
  setTimeout(() => {
    try {
      vditor.insertMD(`[[${targetTitle}]]`)
    } catch (e) {
      const cur = vditor.getValue() || ''
      vditor.setValue(cur + '\n\n[[' + targetTitle + ']]\n')
    }
    existingTitles.value.add(targetTitle)
    showTip(`已插入 [[${targetTitle}]] — Ctrl+点击可跳转，保存后建立双向链接`)
  }, 30)
}

function goNote(id) { router.push(`/knowledge/note/${id}`) }

// ---- [[wiki 链接]] 编辑器内跳转 ----
// 编辑区(IR模式): Ctrl+点击 跳转 (普通点击保留光标编辑, Obsidian 同款交互)
// 预览模式: 直接点击跳转
function handleVditorClick(e) {
  if (e.target.closest && e.target.closest('.side-panel, .vditor-toolbar')) return
  const inPreview = e.target.closest && e.target.closest('.vditor-preview')
  if (!inPreview && !(e.ctrlKey || e.metaKey)) return
  // 拖选文本时不触发
  const sel = window.getSelection()
  if (sel && sel.toString()) return

  // 坐标 → 点击处的文本节点 + 节点内偏移
  let node = null, offset = 0
  if (document.caretRangeFromPoint) {
    const range = document.caretRangeFromPoint(e.clientX, e.clientY)
    if (range) { node = range.startContainer; offset = range.startOffset }
  } else if (document.caretPositionFromPoint) {
    const pos = document.caretPositionFromPoint(e.clientX, e.clientY)
    if (pos) { node = pos.offsetNode; offset = pos.offset }
  }
  if (!node || node.nodeType !== Node.TEXT_NODE) return

  // 关键: vditor IR 模式把 [[ ]] 等语法字符拆进独立 span (文本节点被切碎),
  // 不能只看当前节点 —— 找到所在段落块, TreeWalker 拼接全部文本后再匹配
  // (IR 模式文本不一定包在 p 里, 找不到块级容器时回退到编辑器内容根)
  const block = (node.parentElement && node.parentElement.closest(
    'p, h1, h2, h3, h4, h5, h6, li, blockquote, td, th'
  )) || (e.target.closest('.vditor-ir, .vditor-wysiwyg, .vditor-reset, .vditor-preview'))
  if (!block) return

  let text = ''
  let targetAbs = -1
  const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT)
  let n
  while ((n = walker.nextNode())) {
    if (n === node) targetAbs = text.length + offset
    text += n.textContent
  }
  if (targetAbs < 0) return

  // 点击偏移落在哪个 [[标题]] 里就跳哪个
  const re = /\[\[([^\[\]\n]{1,120})\]\]/g
  let m
  while ((m = re.exec(text))) {
    if (targetAbs >= m.index && targetAbs <= m.index + m[0].length) {
      jumpToWiki(m[1].trim())
      return
    }
  }
}

async function jumpToWiki(t) {
  if (!t) return
  const id = titleIdMap.value.get(t)
  if (id) { router.push(`/knowledge/note/${id}`); return }
  // 虚节点: 目标笔记不存在 → 创建后再跳
  const created = await kbCreateNote(t, `# ${t}\n\n`)
  if (created.success) {
    existingTitles.value.add(t)
    titleIdMap.value.set(t, created.id)
    router.push(`/knowledge/note/${created.id}`)
  }
}

// ---- AI 能力 ----
async function aiTidy() {
  if (aiBusy.value || !vditor) return
  if (!confirm('AI 将重新整理当前笔记内容（覆盖编辑器），确定继续？')) return
  aiBusy.value = true
  try {
    const result = await kbTidy(noteId.value)
    if (result.success) {
      vditor.setValue(result.content)
    } else {
      alert(result.message || 'AI 整理失败')
    }
  } finally {
    aiBusy.value = false
  }
}

async function aiCategory() {
  if (aiBusy.value) return
  aiBusy.value = true
  try {
    const result = await kbAutoCategory(noteId.value)
    if (result.success) {
      category.value = result.category
      if (result.tags?.length && !tagsInput.value.trim()) {
        tagsInput.value = result.tags.join(', ')
      }
    } else {
      alert(result.message || '分类建议失败')
    }
  } finally {
    aiBusy.value = false
  }
}

async function remove() {
  if (!confirm(`确定删除「${title.value}」？此操作不可恢复。`)) return
  const result = await kbDeleteNote(noteId.value)
  if (result.success) router.push('/knowledge')
  else alert(result.message || '删除失败')
}

async function openLink(targetTitle) {
  const id = titleIdMap.value.get(targetTitle)
  if (id) { router.push(`/knowledge/note/${id}`); return }
  const created = await kbCreateNote(targetTitle, `# ${targetTitle}\n\n`)
  if (created.success) {
    existingTitles.value.add(targetTitle)
    titleIdMap.value.set(targetTitle, created.id)
    router.push(`/knowledge/note/${created.id}`)
  }
}

function fmtDate(iso) { return (iso || '').slice(0, 16).replace('T', ' ') }

onMounted(async () => {
  // 从图谱虚节点/链接跳转创建: /knowledge/new?title=xxx 预填标题
  if (isNew.value && route.query.title) {
    title.value = String(route.query.title).slice(0, 120)
  }
  await load()
  await loadRefData()
  await nextTick()
  if (!error.value) {
    initVditor()
    vditorEl.value.addEventListener('click', handleVditorClick)
    if (!isNew.value) doSearch()   // 打开即默认检索
  }
})

// 同组件路由跳转 (Ctrl+点击 [[链接]] 笔记A→B, 或新建保存后 replace 到 /note/:id):
// Vue Router 复用组件实例、不重跑 onMounted —— 必须手动切换笔记数据与编辑器内容,
// 否则 URL 变了但页面还停在原笔记 (要刷新才看到跳转的根因)
watch(() => route.params.id, async (newId, oldId) => {
  if (!newId || newId === oldId) return
  error.value = ''
  await load(true)
  if (vditor) vditor.setValue(note.value?.content || '')
  searchQuery.value = note.value?.title || ''
  await loadRefData()   // 刷新标题→id 映射与反链
  doSearch()
  // 页面是内部容器滚动, 把编辑区滚回顶部
  const sc = document.querySelector('.editor-body')
  if (sc) sc.scrollTop = 0
})

onBeforeUnmount(() => {
  if (vditorEl.value) vditorEl.value.removeEventListener('click', handleVditorClick)
  if (vditor) vditor.destroy()
})
</script>

<style scoped>
.kb-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.kb-container {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 14px 20px;
}

.editor-status { text-align: center; color: var(--text-muted); padding: 60px 0; }

.wiki-insert-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  margin-bottom: 6px;
  font-size: 12px;
  color: #6d28d9;
  background: #f5f3ff;
  border: 1px solid #ddd6fe;
  border-radius: 8px;
}

.side-panel-hint {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 6px;
  line-height: 1.5;
}

.editor-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.editor-title-row { display: flex; align-items: center; gap: 10px; flex: 1; min-width: 260px; }

.editor-title-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  padding: 4px 0;
  border-bottom: 2px solid transparent;
  min-width: 120px;
}

.editor-title-input:focus { border-bottom-color: var(--border-strong); }

.url-open-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: #c2410c;
  text-decoration: none;
  flex-shrink: 0;
  padding: 3px 10px;
  border: 1px solid #ffedd5;
  border-radius: 999px;
  background: #fff7ed;
}

.url-open-link:hover { background: #ffedd5; }

.editor-actions { display: flex; gap: 8px; flex-shrink: 0; align-items: center; }

.editor-action-btn { padding: 7px 12px; font-size: 13px; }
.editor-save-btn { padding: 7px 18px; font-size: 14px; }
.editor-del-btn { padding: 7px 14px; font-size: 14px; color: var(--error); }
.editor-ai-cat-btn { padding: 4px 10px; font-size: 12px; }

.editor-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.editor-cat { max-width: 180px; font-size: 13px; }
.editor-tags { max-width: 340px; font-size: 13px; }
.editor-date { font-size: 12px; color: var(--text-faint); }

.editor-body {
  flex: 1;
  min-height: 0;
  display: grid;
  /* minmax(0,1fr): 防止 Vditor 内宽表格/长行把列撑破导致整页横向滚动 */
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 14px;
  align-items: stretch;
}

.editor-main {
  padding: 6px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* Vditor 会把 height 配置以内联样式写到宿主元素上,
   因此外层 wrap 必须有确定高度(flex 拉伸), 宿主的 100% 才能解析,
   内容在编辑器内部滚动, 页面不再被撑成超长文档 */
.vditor-wrap { flex: 1; min-height: 0; }

.vditor-host { height: 100%; overflow: hidden; }

.editor-side {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  overflow-y: auto;
  padding-right: 2px;
}

.side-panel { padding: 14px; flex-shrink: 0; }

.side-panel-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-faint);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
}

.side-panel-empty { font-size: 13px; color: var(--text-faint); }

.side-link-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  font-size: 13px;
  color: var(--brand-600);
  text-decoration: none;
  padding: 5px 8px;
  border-radius: var(--radius-sm);
}

.side-link-item:hover { background: var(--surface-raised); }
.side-link-item.virtual { color: var(--text-faint); }

.virtual-mark {
  font-size: 11px;
  border: 1px dashed var(--border-strong);
  border-radius: 999px;
  padding: 0 6px;
  color: var(--text-faint);
  flex-shrink: 0;
}

.original-file-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--surface-raised, #f8fafc);
  text-decoration: none;
  color: var(--text-primary);
}
.original-file-link:hover { background: var(--surface-overlay, #f1f5f9); }
.file-icon { font-size: 16px; flex-shrink: 0; }
.file-name { flex: 1; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-open { font-size: 12px; color: var(--brand-600); flex-shrink: 0; }

/* 检索结果 */
.sparse-tip {
  font-size: 12.5px;
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fde68a;
  border-radius: 8px;
  padding: 8px 10px;
  margin-bottom: 8px;
  line-height: 1.5;
}

.search-hit {
  padding: 8px;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  margin-bottom: 8px;
}

.search-hit-head { display: flex; align-items: center; gap: 6px; }

.search-hit-title {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.search-hit-score { font-size: 11px; color: var(--text-faint); flex-shrink: 0; }

.search-hit-excerpt {
  font-size: 12px;
  color: var(--text-muted);
  margin: 4px 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.search-hit-actions { display: flex; gap: 10px; }

.mini-link { font-size: 12px; color: var(--text-muted); text-decoration: none; }
.mini-link:hover { color: var(--text-primary); }
.mini-link.primary { color: var(--brand-600); font-weight: 600; }

.kb-type-badge {
  width: 22px; height: 22px;
  border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px;
  flex-shrink: 0;
}

.kb-type-badge.small { width: 18px; height: 18px; font-size: 10px; }
.kb-type-badge.note { background: #dbeafe; color: #1d4ed8; }
.kb-type-badge.file { background: #dcfce7; color: #15803d; }
.kb-type-badge.url { background: #ffedd5; color: #c2410c; }

@media (max-width: 700px) {
  .kb-page { height: auto; overflow: visible; }
  .editor-body { grid-template-columns: 1fr; }
  /* 窄屏下给 wrap 确定高度(flex:none 使 height 生效), 宿主内联 100% 可解析, 内容在编辑器内部滚动 */
  .vditor-wrap { flex: none; height: 70vh; }
  .editor-side { overflow: visible; }
}
</style>
