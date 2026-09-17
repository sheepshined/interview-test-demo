<template>
  <div class="kb-chat-page">
    <TopNav back-text="返回知识库" />

    <div class="kb-chat-container">
      <!-- 左侧: 会话列表 -->
      <aside class="kc-sidebar">
        <div class="kc-side-header">
          <button class="kc-new-btn" @click="createAndSwitch">
            <DSIcon name="plus" :size="16" />新对话
          </button>
        </div>

        <div class="kc-sessions">
          <div v-for="s in sessions" :key="s.id"
               class="kc-sess-item"
               :class="{ active: currentId === s.id }"
               @click="switchTo(s.id)">
            <div class="kc-sess-title">{{ s.title || '新对话' }}</div>
            <div class="kc-sess-time">{{ fmtTime(s.updated_at) }}</div>
            <div class="kc-sess-actions" @click.stop>
              <button class="kc-sess-del" title="删除" @click="deleteSess(s.id)">
                <DSIcon name="trash-2" :size="13" />
              </button>
            </div>
          </div>
          <div v-if="!sessions.length" class="kc-side-empty">还没有对话</div>
        </div>
      </aside>

      <!-- 右侧: 聊天区 -->
      <main class="kc-main">
        <template v-if="currentId">
          <!-- 消息区 -->
          <div class="kc-messages" ref="messagesEl">
            <div v-for="(msg, i) in messages" :key="i" class="kc-msg" :class="msg.role">
              <div class="kc-msg-avatar">
                <DSIcon v-if="msg.role === 'assistant'" name="message-circle" :size="16" />
                <DSIcon v-else name="user" :size="16" />
              </div>
              <div class="kc-msg-body">
                <div class="kc-msg-text" v-html="formatAnswer(msg.content)"></div>
                <div v-if="msg.sources?.length" class="kc-sources">
                  <div class="kc-sources-title">
                    <DSIcon name="book-open" :size="12" />参考来源
                  </div>
                  <a v-for="s in msg.sources" :key="s.note_id" class="kc-source-link"
                     :href="`/knowledge/note/${s.note_id}`" @click.prevent="goNote(s.note_id)">
                    <span class="kc-source-title">{{ s.title }}</span>
                    <span class="kc-source-score">{{ (s.score * 100).toFixed(0) }}%</span>
                  </a>
                </div>
                <div v-if="msg.sparse" class="kc-sparse-tip">
                  <DSIcon name="triangle-alert" :size="13" />
                  <span>相关度不高，可能需要先导入更多相关资料</span>
                  <router-link to="/knowledge" class="kc-sparse-link">去导入 →</router-link>
                </div>
              </div>
            </div>

            <!-- 正在思考 -->
            <div v-if="loading" class="kc-msg assistant">
              <div class="kc-msg-avatar"><DSIcon name="message-circle" :size="16" /></div>
              <div class="kc-msg-body">
                <div class="kc-thinking"><span></span><span></span><span></span></div>
              </div>
            </div>
          </div>

          <!-- 空消息提示 -->
          <div v-if="!messages.length && !loading" class="kc-empty">
            <div class="kc-empty-ic"><DSIcon name="book-open" :size="48" color="#a5b4fc" /></div>
            <p>开始向你的知识库提问吧</p>
            <div class="kc-suggestions">
              <button v-for="s in suggestions" :key="s" class="kc-suggest-btn" @click="send(s)">{{ s }}</button>
            </div>
          </div>

          <!-- 输入区 -->
          <div class="kc-input-area">
            <div class="kc-input-wrap">
              <textarea v-model="input" class="kc-input" rows="2"
                        placeholder="输入你的问题，比如：注意力机制和 self-attention 有什么区别？"
                        :disabled="loading"
                        @keydown.enter.exact.prevent="send" />
              <button class="kc-send-btn" :disabled="loading || !input.trim()" @click="send">
                <DSIcon name="arrow-right" :size="18" color="#fff" />
              </button>
            </div>
            <div class="kc-hint">回答基于你的知识库内容生成，低相关度时可能不准确</div>
          </div>
        </template>

        <!-- 未选中会话 -->
        <div v-else class="kc-unselected">
          <div class="kc-unsel-ic"><DSIcon name="message-circle" :size="56" color="#a5b4fc" /></div>
          <h3>欢迎使用知识库 AI 对话</h3>
          <p>基于你的笔记和资料提问，AI 会检索知识库内容回答并标注来源</p>
          <button class="ds-btn ds-btn-primary kc-start-btn" @click="createAndSwitch">
            <DSIcon name="plus" :size="16" />开始新对话
          </button>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import TopNav from '../../components/TopNav.vue'
import DSIcon from '../../components/DSIcon.vue'
import { renderMarkdown } from '../../utils/markdown'
import {
  kbQa, kbChatListSessions, kbChatCreateSession,
  kbChatGetSession, kbChatDeleteSession,
} from '../../api'

const router = useRouter()

const sessions = ref([])
const currentId = ref(null)
const messages = ref([])
const input = ref('')
const loading = ref(false)
const messagesEl = ref(null)

const suggestions = [
  '注意力机制和 self-attention 有什么区别？',
  'Transformer 的核心架构是什么？',
  'RAG 的检索增强生成流程是怎样的？',
]

function fmtTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const now = new Date()
    const diff = (now - d) / 1000
    if (diff < 60) return '刚刚'
    if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
    if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
    if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} 天前`
    return d.toLocaleDateString()
  } catch { return iso }
}

function goNote(id) { router.push(`/knowledge/note/${id}`) }

function formatAnswer(text) {
  return renderMarkdown(text)
}

async function loadSessions() {
  const r = await kbChatListSessions()
  if (r.success) sessions.value = r.sessions
}

async function switchTo(id) {
  if (currentId.value === id) return
  currentId.value = id
  messages.value = []
  const r = await kbChatGetSession(id)
  if (r.success) {
    messages.value = r.messages || []
    await scrollBottom()
  }
}

async function createAndSwitch() {
  const r = await kbChatCreateSession()
  if (r.success) {
    sessions.value.unshift(r.session)
    await switchTo(r.session.id)
  }
}

async function deleteSess(id) {
  if (!confirm('确定删除这个对话吗？')) return
  const r = await kbChatDeleteSession(id)
  if (r.success) {
    sessions.value = sessions.value.filter(s => s.id !== id)
    if (currentId.value === id) {
      currentId.value = null
      messages.value = []
    }
  }
}

async function send(question) {
  const q = ((typeof question === 'string' ? question : input.value) || '').trim()
  if (!q || loading.value) return
  input.value = ''
  messages.value.push({ role: 'user', content: q })
  loading.value = true
  await scrollBottom()

  try {
    const r = await kbQa(q, 5, currentId.value)
    if (r.success) {
      // 如果没有 sessionId 说明是新建会话，后端会返回
      if (r.session_id && !currentId.value) {
        currentId.value = r.session_id
        await loadSessions()
      }
      messages.value.push({
        role: 'assistant',
        content: r.answer,
        sources: r.sources || [],
        sparse: r.sparse,
      })
      // 更新会话列表（标题可能被后端自动生成了）
      await loadSessions()
    } else {
      messages.value.push({ role: 'assistant', content: r.error || '请求失败' })
    }
  } catch (e) {
    messages.value.push({ role: 'assistant', content: '网络错误，请稍后重试' })
  } finally {
    loading.value = false
    await scrollBottom()
  }
}

async function scrollBottom() {
  await nextTick()
  if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
}

onMounted(async () => {
  await loadSessions()
  // 自动选中最新的一个（如果有）
  if (sessions.value.length) {
    await switchTo(sessions.value[0].id)
  }
})
</script>

<style scoped>
.kb-chat-page { height: 100%; display: flex; flex-direction: column; background: var(--bg-100); }

.kb-chat-container {
  flex: 1; min-height: 0;
  display: grid;
  grid-template-columns: 220px 1fr;
  min-width: 0;
}

/* 左侧会话列表 */
.kc-sidebar {
  border-right: 1px solid var(--border-color, #e5e7eb);
  background: #fafafa;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.kc-side-header { padding: 14px 12px; border-bottom: 1px solid var(--border-color, #e5e7eb); }

.kc-new-btn {
  width: 100%;
  padding: 9px 12px;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  background: var(--brand-700, #4338ca);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center; gap: 6px;
  transition: background 0.15s;
}
.kc-new-btn:hover { background: var(--brand-800, #3730a3); }

.kc-sessions {
  flex: 1; overflow-y: auto; padding: 8px;
}
.kc-side-empty { text-align: center; color: var(--text-faint); font-size: 12px; padding: 24px 8px; }

.kc-sess-item {
  padding: 10px 12px;
  border-radius: 8px;
  margin-bottom: 4px;
  cursor: pointer;
  transition: background 0.12s;
  position: relative;
}
.kc-sess-item:hover { background: #f3f4f6; }
.kc-sess-item.active { background: var(--brand-50, #eef2ff); }
.kc-sess-item.active .kc-sess-title { color: var(--brand-800, #3730a3); }

.kc-sess-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.kc-sess-time {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.kc-sess-actions {
  position: absolute;
  right: 6px; top: 50%; transform: translateY(-50%);
  opacity: 0; transition: opacity 0.12s;
}
.kc-sess-item:hover .kc-sess-actions { opacity: 1; }
.kc-sess-del {
  width: 26px; height: 26px;
  border: none; background: transparent;
  border-radius: 6px;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-faint);
  transition: all 0.12s;
}
.kc-sess-del:hover { background: #fee2e2; color: #dc2626; }

/* 右侧聊天区 */
.kc-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.kc-unselected {
  flex: 1;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 14px;
  padding: 40px;
  text-align: center;
}
.kc-unselected h3 { margin: 0; font-size: 18px; font-weight: 600; }
.kc-unselected p { margin: 0; color: var(--text-muted); font-size: 13px; max-width: 400px; }
.kc-start-btn { padding: 10px 20px; display: flex; align-items: center; gap: 6px; }

/* 消息区 */
.kc-messages {
  flex: 1; min-height: 0; overflow-y: auto;
  padding: 20px 28px;
  display: flex; flex-direction: column; gap: 16px;
}

.kc-msg { display: flex; gap: 10px; max-width: 80%; }
.kc-msg.user { align-self: flex-end; flex-direction: row-reverse; }
.kc-msg.assistant { align-self: flex-start; }

.kc-msg-avatar {
  width: 32px; height: 32px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.kc-msg.assistant .kc-msg-avatar { background: var(--brand-50, #eef2ff); color: var(--brand-700, #4338ca); }
.kc-msg.user .kc-msg-avatar { background: #f3f4f6; color: var(--text-secondary); }

.kc-msg-body {
  background: #fff;
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid var(--border-color, #e5e7eb);
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.kc-msg.user .kc-msg-body { background: var(--brand-700, #4338ca); border-color: transparent; color: #fff; }

.kc-msg-text { font-size: 14px; line-height: 1.7; word-break: break-word; overflow-wrap: anywhere; }
.kc-msg-text :deep(.md-p) { margin: 0 0 8px; }
.kc-msg-text :deep(.md-p:last-child) { margin-bottom: 0; }
.kc-msg-text :deep(.md-h) { margin: 14px 0 8px; line-height: 1.4; font-weight: 700; }
.kc-msg-text :deep(.md-h1) { font-size: 18px; }
.kc-msg-text :deep(.md-h2) { font-size: 16px; padding-bottom: 4px; border-bottom: 1px solid rgba(0,0,0,0.08); }
.kc-msg-text :deep(.md-h3) { font-size: 15px; }
.kc-msg-text :deep(.md-h4) { font-size: 14px; }
.kc-msg-text :deep(.md-hr) { border: none; border-top: 1px solid rgba(0,0,0,0.12); margin: 12px 0; }
.kc-msg-text :deep(.md-ul),
.kc-msg-text :deep(.md-ol) { margin: 6px 0; padding-left: 22px; }
.kc-msg-text :deep(.md-ul li) { list-style: disc; margin: 3px 0; }
.kc-msg-text :deep(.md-ol li) { list-style: decimal; margin: 3px 0; }
.kc-msg-text :deep(.md-quote) {
  margin: 8px 0; padding: 6px 12px;
  border-left: 3px solid #a5b4fc; background: rgba(99,102,241,0.06);
  color: inherit; border-radius: 0 6px 6px 0;
}
.kc-msg-text :deep(.md-pre) {
  margin: 8px 0; padding: 12px 14px;
  background: #0f172a; color: #e2e8f0;
  border-radius: 8px; overflow-x: auto;
  font-size: 12.5px; line-height: 1.6;
}
.kc-msg-text :deep(.md-code-block) { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.kc-msg-text :deep(.md-code-inline) {
  background: rgba(0,0,0,0.06); border-radius: 4px;
  padding: 1px 5px; font-size: 12.5px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
.kc-msg-text :deep(.md-link) { color: #4f46e5; text-decoration: none; }
.kc-msg-text :deep(.md-link:hover) { text-decoration: underline; }
.kc-msg-text :deep(.md-table) {
  border-collapse: collapse; margin: 8px 0; font-size: 13px;
  display: block; overflow-x: auto; max-width: 100%;
}
.kc-msg-text :deep(.md-table th),
.kc-msg-text :deep(.md-table td) {
  border: 1px solid rgba(0,0,0,0.12); padding: 6px 10px; text-align: left;
}
.kc-msg-text :deep(.md-table th) { background: rgba(0,0,0,0.04); font-weight: 600; }
/* 用户气泡(深底)上的代码/表格反色 */
.kc-msg.user .kc-msg-text :deep(.md-code-inline) { background: rgba(255,255,255,0.18); color: #fff; }
.kc-msg.user .kc-msg-text :deep(.md-quote) { background: rgba(255,255,255,0.12); border-left-color: rgba(255,255,255,0.7); }
.kc-msg.user .kc-msg-text :deep(.md-link) { color: #fef08a; }
.kc-msg.user .kc-msg-text :deep(.md-table th),
.kc-msg.user .kc-msg-text :deep(.md-table td) { border-color: rgba(255,255,255,0.35); }
.kc-msg.user .kc-msg-text :deep(.md-table th) { background: rgba(255,255,255,0.12); }
.kc-msg.user .kc-msg-text :deep(.md-hr) { border-top-color: rgba(255,255,255,0.35); }

.kc-sources { margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--border-color, #e5e7eb); }
.kc-sources-title { font-size: 11px; color: var(--text-muted); display: flex; align-items: center; gap: 4px; margin-bottom: 6px; font-weight: 600; }
.kc-source-link { display: flex; justify-content: space-between; align-items: center; padding: 5px 10px; margin-bottom: 4px; background: var(--brand-50, #eef2ff); border-radius: 6px; text-decoration: none; font-size: 12px; transition: background 0.15s; }
.kc-source-link:hover { background: var(--brand-100, #e0e7ff); }
.kc-source-title { color: var(--brand-800, #3730a3); }
.kc-source-score { color: var(--text-muted); font-size: 11px; }

.kc-sparse-tip { margin-top: 10px; padding: 8px 12px; background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; display: flex; align-items: center; gap: 6px; font-size: 12px; color: #92400e; }
.kc-sparse-link { color: #b45309; font-weight: 600; text-decoration: none; margin-left: auto; }

.kc-thinking { display: flex; gap: 4px; padding: 4px 0; }
.kc-thinking span { width: 8px; height: 8px; background: #a5b4fc; border-radius: 50%; animation: think 1.2s infinite ease-in-out; }
.kc-thinking span:nth-child(2) { animation-delay: 0.15s; }
.kc-thinking span:nth-child(3) { animation-delay: 0.3s; }
@keyframes think { 0%,80%,100% { transform: scale(0.6); opacity: 0.5; } 40% { transform: scale(1); opacity: 1; } }

/* 空会话提示 */
.kc-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px; padding: 40px 20px; }
.kc-empty-ic { width: 80px; height: 80px; background: var(--brand-50, #eef2ff); border-radius: 50%; display: flex; align-items: center; justify-content: center; }
.kc-empty p { color: var(--text-muted); margin: 0; font-size: 14px; }
.kc-suggestions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.kc-suggest-btn { padding: 8px 14px; font-size: 13px; border: 1px solid var(--border-color, #e5e7eb); background: #fff; border-radius: 8px; cursor: pointer; color: var(--text-secondary); transition: all 0.15s; }
.kc-suggest-btn:hover { border-color: var(--brand-300, #c7d2fe); color: var(--brand-700, #4338ca); background: var(--brand-50, #eef2ff); }

/* 输入区 */
.kc-input-area { flex-shrink: 0; padding: 16px 28px 24px; }
.kc-input-wrap { display: flex; gap: 8px; background: #fff; border: 1px solid var(--border-color, #e5e7eb); border-radius: 12px; padding: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.kc-input-wrap:focus-within { border-color: var(--brand-400, #818cf8); box-shadow: 0 0 0 3px rgba(129,140,248,0.15); }
.kc-input { flex: 1; border: none; outline: none; resize: none; font-size: 14px; line-height: 1.5; padding: 4px 8px; background: transparent; font-family: inherit; }
.kc-send-btn { width: 36px; height: 36px; background: var(--brand-700, #4338ca); border: none; border-radius: 10px; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; transition: background 0.15s; }
.kc-send-btn:hover:not(:disabled) { background: var(--brand-800, #3730a3); }
.kc-send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.kc-hint { font-size: 11px; color: var(--text-faint, #9ca3af); text-align: center; margin-top: 8px; }

@media (max-width: 720px) {
  .kb-chat-container { grid-template-columns: 1fr; }
  .kc-sidebar { display: none; }
}
</style>
