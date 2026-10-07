<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Icon from '../../components/Icon.vue'
import TopBar from '../../components/TopBar.vue'
import { toast } from '../../composables/useToast'
import { renderMarkdown } from '../../utils/markdown'
import {
  kbGetNote, kbCreateNote, kbUpdateNote, kbDeleteNote, kbCategories,
  kbSearch, kbTidy, kbAutoCategory, kbAutoLink, kbFileUrl,
} from '../../api'

const route = useRoute()
const router = useRouter()

const noteId = computed(() => (route.params.id ? Number(route.params.id) : null))
const isNew = computed(() => !noteId.value)

const note = ref(null)
const title = ref('')
const content = ref('')
const category = ref('')
const tagsInput = ref('')
const backlinks = ref([])
const related = ref([])
const categories = ref([])

const loading = ref(!isNew.value)
const error = ref('')
const saving = ref(false)
const aiBusy = ref(false)
const aiAction = ref('')
const mode = ref('edit')   // 'edit' | 'preview'

const typeLabel = computed(() =>
  ({ note: '手写笔记', file: '文件导入', url: '网址收藏' }[note.value?.note_type] || '手写笔记'))
const typeIcon = computed(() =>
  ({ note: 'pen', file: 'file', url: 'link' }[note.value?.note_type] || 'pen'))
const wordCount = computed(() => (content.value || '').replace(/\s+/g, '').length)
const fileUrl = computed(() => (note.value?.file_path ? kbFileUrl(note.value.file_path) : ''))

// 预览：先安全渲染 Markdown，再把 [[标题]] 后处理为 .wikilink（内容已被 markdown 转义，XSS 安全）
function buildPreview(md) {
  const html = renderMarkdown(md || '')
  return html.replace(/\[\[([^\[\]<>\n]{1,120})\]\]/g, (m, raw) => {
    const name = raw.trim()
    if (!name) return m
    return `<span class="wikilink" data-wiki="${name}">${name}</span>`
  })
}
const previewHtml = computed(() => buildPreview(content.value))

function fmtDate(iso) { return (iso || '').slice(0, 10) }
function fmtDateTime(iso) { return (iso || '').slice(0, 16).replace('T', ' ') }

async function load(silent = false) {
  if (isNew.value) { loading.value = false; return }
  if (!silent) loading.value = true
  error.value = ''
  try {
    const result = await kbGetNote(noteId.value)
    if (!result.success) { error.value = result.message || '笔记不存在'; return }
    note.value = result.note
    title.value = result.note.title || ''
    content.value = result.note.content || ''
    category.value = result.note.category || ''
    tagsInput.value = (result.note.tags || []).join(', ')
    backlinks.value = result.backlinks || []
  } finally {
    if (!silent) loading.value = false
  }
}

async function loadCategories() {
  const result = await kbCategories()
  if (result.success) categories.value = result.categories || []
}

async function loadRelated() {
  const q = (title.value || content.value || '').trim()
  if (!q) { related.value = []; return }
  const result = await kbSearch(q.slice(0, 200), 6)
  if (result.success) {
    related.value = (result.results || [])
      .filter((r) => r.note_id !== noteId.value)
      .slice(0, 4)
  }
}

async function save() {
  if (saving.value) return
  const t = title.value.trim()
  if (!t) { toast('请填写笔记标题', 'warn'); return }
  saving.value = true
  try {
    const tags = tagsInput.value.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
    const result = isNew.value
      ? await kbCreateNote(t, content.value, tags, category.value.trim())
      : await kbUpdateNote(noteId.value, t, content.value, tags, category.value.trim())
    if (!result.success) { toast(result.message || '保存失败', 'warn'); return }
    if (isNew.value) {
      toast('已创建笔记')
      router.replace(`/knowledge/note/${result.id}`)
      await loadCategories()
    } else {
      await load(true)
      await Promise.all([loadRelated(), loadCategories()])
      toast('已保存 · 已同步向量索引')
    }
  } finally {
    saving.value = false
  }
}

async function remove() {
  if (isNew.value) return
  if (!confirm(`确定删除「${title.value}」？此操作不可恢复。`)) return
  const result = await kbDeleteNote(noteId.value)
  if (result.success) { toast('已删除该笔记'); router.push('/knowledge') }
  else toast(result.message || '删除失败', 'warn')
}

// ---- AI 动作（均需先保存拿到 noteId） ----
async function aiTidy() {
  if (aiBusy.value || isNew.value) return
  if (!confirm('AI 将重新整理当前笔记内容（覆盖编辑区），确定继续？')) return
  aiBusy.value = true; aiAction.value = 'tidy'
  try {
    const result = await kbTidy(noteId.value)
    if (result.success) {
      content.value = result.content || ''
      toast('AI 整理排版完成，请记得保存', 'sparkle')
    } else {
      toast(result.message || 'AI 整理失败', 'warn')
    }
  } finally {
    aiBusy.value = false; aiAction.value = ''
  }
}

async function aiCategory() {
  if (aiBusy.value || isNew.value) return
  aiBusy.value = true; aiAction.value = 'category'
  try {
    const result = await kbAutoCategory(noteId.value)
    if (result.success) {
      if (result.category) category.value = result.category
      if (result.tags?.length && !tagsInput.value.trim()) tagsInput.value = result.tags.join(', ')
      toast(`已自动归类到「${result.category || '未分类'}」`, 'folder')
    } else {
      toast(result.message || '分类建议失败', 'warn')
    }
  } finally {
    aiBusy.value = false; aiAction.value = ''
  }
}

async function smartLink() {
  if (aiBusy.value || isNew.value) return
  aiBusy.value = true; aiAction.value = 'link'
  try {
    const result = await kbAutoLink(noteId.value)
    if (result.success) {
      if (result.linked?.length) {
        await load(true)
        await loadRelated()
        toast(`已智能关联 ${result.linked.length} 篇：${result.linked.join('、')}`, 'link')
      } else {
        toast(result.message || '暂无足够相关的笔记可关联', 'warn')
      }
    } else {
      toast(result.message || '智能关联失败', 'warn')
    }
  } finally {
    aiBusy.value = false; aiAction.value = ''
  }
}

// ---- [[wiki 链接]] 跳转 ----
async function openWiki(name) {
  if (!name) return
  const result = await kbSearch(name, 5)
  const list = (result.success && result.results) || []
  const hit = list.find((x) => x.title === name) || list[0]
  if (hit) router.push(`/knowledge/note/${hit.note_id}`)
  else toast(`未找到「${name}」，可在笔记列表新建`, 'warn')
}

function onPreviewClick(e) {
  const el = e.target.closest?.('.wikilink')
  if (el) openWiki(el.dataset.wiki)
}

function insertRelated(item) {
  const t = item.title
  const cur = content.value || ''
  content.value = cur + (cur && !cur.endsWith('\n') ? '\n\n' : '') + `- [[${t}]]`
  mode.value = 'edit'
  toast(`已插入 [[${t}]]`)
}

onMounted(async () => {
  if (isNew.value && route.query.title) {
    title.value = String(route.query.title).slice(0, 120)
  }
  await load()
  await Promise.all([loadCategories(), loadRelated()])
})

// 同组件路由跳转（新建保存后 replace / 点击反链）：手动切换笔记数据
watch(() => route.params.id, async (newId, oldId) => {
  if (!newId || newId === oldId) return
  error.value = ''
  await load(true)
  await loadRelated()
})
</script>

<template>
  <div>
    <TopBar crumb="笔记编辑" folio="卷·05">
      <template #actions>
        <button v-if="!isNew" class="icon-btn" title="删除笔记" @click="remove">
          <Icon name="trash" :size="15" />
        </button>
        <button class="btn btn-sm" :disabled="saving || !title.trim()" @click="save">
          <Icon name="save" :size="15" />{{ saving ? '保存中…' : (isNew ? '创建' : '保存') }}
        </button>
      </template>
    </TopBar>

    <div class="page-body">
      <div v-if="loading" class="editor-status">加载中…</div>
      <div v-else-if="error" class="editor-status" style="color:var(--vermilion)">{{ error }}</div>

      <div v-else class="editor-layout">
        <!-- ══ 编辑器 ══ -->
        <div class="editor" v-reveal>
          <div class="editor-head">
            <div class="type-row">
              <span class="badge line"><Icon :name="typeIcon" :size="13" />{{ typeLabel }}</span>
              <span class="mono">
                {{ isNew ? 'NEW NOTE · 尚未保存' : `NOTE № ${noteId} · 创建于 ${fmtDate(note?.created_at)}` }}
              </span>
            </div>
            <input v-model="title" class="title-input" placeholder="笔记标题" />
            <div class="editor-meta">
              <span class="mini-field">
                <Icon name="folder" :size="14" />分类
                <input v-model="category" list="kb-cat-list" placeholder="未分类" />
              </span>
              <span class="mini-field">
                <Icon name="hash" :size="14" />标签
                <input v-model="tagsInput" placeholder="逗号分隔" />
              </span>
              <datalist id="kb-cat-list">
                <option v-for="c in categories" :key="c.category" :value="c.category" />
              </datalist>
            </div>
          </div>

          <div class="editor-toolbar">
            <button class="tool-btn" :disabled="isNew || aiBusy" @click="aiTidy">
              <Icon name="sparkle" :size="14" />{{ aiAction === 'tidy' ? '处理中…' : '整理排版' }}
            </button>
            <button class="tool-btn" :disabled="isNew || aiBusy" @click="aiCategory">
              <Icon name="folder" :size="14" />{{ aiAction === 'category' ? '处理中…' : '自动分类' }}
            </button>
            <button class="tool-btn" :disabled="isNew || aiBusy" @click="smartLink">
              <Icon name="link" :size="14" />{{ aiAction === 'link' ? '处理中…' : '智能关联' }}
            </button>
            <div class="seg">
              <button :class="{ 'is-on': mode === 'edit' }" @click="mode = 'edit'">编辑</button>
              <button :class="{ 'is-on': mode === 'preview' }" @click="mode = 'preview'">预览</button>
            </div>
          </div>

          <div class="paper-area">
            <textarea v-model="content" spellcheck="false" :class="{ 'is-off': mode === 'preview' }"
                      placeholder="用 Markdown 记录知识，输入 [[标题]] 链接其他笔记…"></textarea>
            <div class="preview" :class="{ 'is-on': mode === 'preview' }"
                 @click="onPreviewClick" v-html="previewHtml"></div>
          </div>
        </div>

        <!-- ══ 右栏 ══ -->
        <aside class="side-stack">
          <div class="panel" v-reveal="0.06">
            <div class="panel-head">元信息 <Icon name="target" :size="14" /></div>
            <div class="panel-body" style="padding-top:6px">
              <div class="kv"><span class="k">类型</span><span class="v">{{ typeLabel }}</span></div>
              <div class="kv"><span class="k">创建</span><span class="v">{{ isNew ? '—' : fmtDate(note?.created_at) }}</span></div>
              <div class="kv"><span class="k">更新</span><span class="v">{{ isNew ? '—' : fmtDateTime(note?.updated_at) }}</span></div>
              <div class="kv"><span class="k">字数</span><span class="v num">{{ wordCount }}</span></div>
              <div class="kv"><span class="k">被引用</span><span class="v num">{{ backlinks.length }}</span></div>
            </div>
          </div>

          <div v-if="fileUrl" class="panel" v-reveal="0.1">
            <div class="panel-head">原始文件 <Icon name="file" :size="14" /></div>
            <div class="panel-body">
              <a class="file-link" :href="fileUrl" target="_blank" :title="note?.file_name || '原始文件'">
                <Icon name="file" :size="14" />
                <span class="fn">{{ note?.file_name || '原始文件' }}</span>
                <span class="fo">打开 <Icon name="external" :size="12" /></span>
              </a>
            </div>
          </div>

          <div class="panel" v-reveal="0.12">
            <div class="panel-head">反向链接 · {{ backlinks.length }} <Icon name="link" :size="14" /></div>
            <div class="panel-body" style="padding-top:6px">
              <div v-if="!backlinks.length" class="panel-empty">还没有笔记链接到这里</div>
              <a v-for="b in backlinks" :key="b.id" class="backlink" href="javascript:void(0)"
                 @click="router.push(`/knowledge/note/${b.id}`)">
                <span class="t"><Icon name="link" :size="14" />{{ b.title }}</span>
                <span class="ctx">更新于 {{ fmtDateTime(b.updated_at) }}</span>
              </a>
            </div>
          </div>

          <div class="panel" v-reveal="0.18">
            <div class="panel-head">相关笔记 · 语义 <Icon name="network" :size="14" /></div>
            <div class="panel-body" style="padding-top:6px">
              <div v-if="!related.length" class="panel-empty">暂无相关笔记</div>
              <div v-for="r in related" :key="r.note_id" class="related">
                <span class="t">{{ r.title }}</span>
                <span class="sim">{{ (r.score * 100).toFixed(0) }}%</span>
                <button class="insert" @click="insertRelated(r)">插入</button>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  </div>
</template>

<style scoped>
  .editor-layout { display: grid; grid-template-columns: 1.6fr 1fr; gap: 26px; align-items: start; }

  /* ── 编辑器 ── */
  .editor { border: 1px solid var(--line-strong); background: var(--sheet); }
  .editor-head { padding: 24px 30px 0; }
  .type-row { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
  .title-input {
    width: 100%; border: 0; background: none; outline: none;
    font-family: var(--f-display); font-weight: 900; font-size: clamp(24px, 2.4vw, 32px);
    line-height: 1.35; color: var(--ink);
  }
  .title-input::placeholder { color: var(--ink-4); }
  .editor-meta { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin: 16px 0 0; }
  .mini-field { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--ink-3); }
  .mini-field input {
    border: 0; border-bottom: 1px dashed var(--line-strong); background: none; outline: none;
    font-size: 13px; padding: 3px 2px; min-width: 90px; color: var(--ink);
  }
  .mini-field input:focus { border-bottom-color: var(--vermilion); }

  .editor-toolbar {
    display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
    padding: 16px 30px; margin-top: 20px;
    border-top: 1px solid var(--line); border-bottom: 1px solid var(--line);
    background: var(--sheet-2);
  }
  .tool-btn {
    display: inline-flex; align-items: center; gap: 7px;
    padding: 8px 13px; font-size: 12.5px;
    border: 1px solid var(--line); background: var(--sheet); color: var(--ink-2);
    transition: all var(--dur-1) ease;
  }
  .tool-btn:hover { border-color: var(--ink); color: var(--ink); transform: translateY(-1px); }
  .tool-btn .ic { color: var(--vermilion); }
  .tool-btn[disabled] { opacity: 0.38; pointer-events: none; }
  .seg { display: flex; margin-left: auto; border: 1px solid var(--line); }
  .seg button { padding: 8px 16px; font-size: 12.5px; color: var(--ink-3); transition: all var(--dur-1) ease; }
  .seg button.is-on { background: var(--ink); color: var(--paper); }

  /* 稿纸 */
  .paper-area { position: relative; }
  .paper-area textarea {
    width: 100%; min-height: 520px; border: 0; outline: none; resize: vertical;
    padding: 26px 30px 34px; background: transparent;
    font-size: 14.5px; line-height: 2.05; color: var(--ink);
    background-image: repeating-linear-gradient(transparent 0, transparent 39px, var(--line-soft) 39px, var(--line-soft) 40px);
    background-position: 0 26px;
  }
  .paper-area textarea::placeholder { color: var(--ink-4); }

  /* 预览（渲染后的 Markdown） */
  .preview { padding: 26px 30px 34px; display: none; }
  .preview.is-on { display: block; }
  .paper-area textarea.is-off { display: none; }
  .preview :deep(h2) { font-size: 20px; margin: 26px 0 10px; }
  .preview :deep(h2:first-child) { margin-top: 0; }
  .preview :deep(h3) { font-size: 16px; margin: 20px 0 8px; color: var(--ink-2); }
  .preview :deep(p) { font-size: 14.5px; line-height: 2.05; color: var(--ink-2); margin-bottom: 12px; }
  .preview :deep(li) { font-size: 14.5px; line-height: 2; color: var(--ink-2); padding-left: 18px; position: relative; }
  .preview :deep(li::before) { content: '·'; position: absolute; left: 5px; color: var(--vermilion); }
  .preview :deep(blockquote) {
    margin: 16px 0; padding: 12px 18px;
    border-left: 2px solid var(--verm-line); background: var(--verm-wash);
    font-size: 13.5px; color: var(--ink-2); font-style: italic;
  }
  .preview :deep(code) {
    font-family: var(--f-mono); font-size: 12.5px;
    background: var(--sheet-2); border: 1px solid var(--line); padding: 1px 6px;
  }
  .preview :deep(.wikilink) {
    color: var(--indigo-ink); font-weight: 500;
    border-bottom: 1px dashed rgba(35,64,92,.5); cursor: pointer;
    transition: all var(--dur-1) ease;
  }
  .preview :deep(.wikilink:hover) { color: var(--vermilion); border-color: var(--vermilion); }

  /* ── 右栏 ── */
  .side-stack { display: flex; flex-direction: column; gap: 20px; }
  .panel { border: 1px solid var(--line); background: var(--sheet); }
  .panel-head {
    padding: 14px 18px; border-bottom: 1px solid var(--line);
    display: flex; align-items: center; justify-content: space-between; gap: 10px;
    font-family: var(--f-mono); font-size: 10.5px; letter-spacing: 0.18em; text-transform: uppercase; color: var(--ink-3);
  }
  .panel-body { padding: 14px 18px; }
  .kv { display: flex; justify-content: space-between; gap: 12px; padding: 7px 0; font-size: 13px; border-bottom: 1px dashed var(--line); }
  .kv:last-child { border-bottom: 0; }
  .kv .k { color: var(--ink-4); font-family: var(--f-mono); font-size: 10.5px; letter-spacing: 0.12em; text-transform: uppercase; padding-top: 2px; }
  .kv .v { color: var(--ink-2); text-align: right; }
  .kv .v.num { font-family: var(--f-mono); font-weight: 700; color: var(--ink); }

  .backlink { display: block; padding: 11px 0; border-bottom: 1px dashed var(--line); }
  .backlink:last-child { border-bottom: 0; }
  .backlink .t { font-size: 13.5px; font-weight: 600; color: var(--ink); display: flex; align-items: center; gap: 7px; }
  .backlink .t .ic { color: var(--indigo-ink); }
  .backlink .ctx { font-size: 12.5px; color: var(--ink-3); line-height: 1.8; margin-top: 5px; display: block; }
  .backlink .ctx em { font-style: normal; background: var(--verm-wash); color: var(--ink); padding: 0 2px; }

  .related { display: flex; align-items: center; gap: 12px; padding: 11px 0; border-bottom: 1px dashed var(--line); }
  .related:last-child { border-bottom: 0; }
  .related .t { flex: 1; min-width: 0; font-size: 13.5px; color: var(--ink-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .related .sim { font-family: var(--f-mono); font-size: 11px; font-weight: 700; color: var(--pine); }
  .related .insert {
    font-family: var(--f-mono); font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase;
    color: var(--ink-4); border: 1px solid var(--line); padding: 3px 8px; opacity: 0;
    transition: all var(--dur-1) ease;
  }
  .related:hover .insert { opacity: 1; }
  .related .insert:hover { color: var(--vermilion); border-color: var(--verm-line); }

  /* 原始文件 */
  .file-link {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 12px; border: 1px solid var(--line); background: var(--sheet-2);
    transition: border-color var(--dur-1) ease;
  }
  .file-link:hover { border-color: var(--line-strong); }
  .file-link .fn { flex: 1; min-width: 0; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .file-link .fo { display: inline-flex; align-items: center; gap: 4px; font-family: var(--f-mono); font-size: 10.5px; color: var(--ink-3); flex-shrink: 0; }

  .panel-empty { font-size: 13px; color: var(--ink-4); }
  .editor-status { text-align: center; color: var(--ink-3); padding: 60px 0; font-size: 14px; }

  @media (max-width: 1080px) { .editor-layout { grid-template-columns: 1fr; } }
  @media (max-width: 620px) {
    .editor-head { padding: 20px 20px 0; }
    .editor-toolbar { padding: 14px 20px; }
    .paper-area textarea, .preview { padding: 20px 20px 28px; }
    .type-row { flex-wrap: wrap; gap: 8px; }
    .type-row .mono { display: none; }
    .editor-meta { gap: 8px 16px; }
  }
</style>