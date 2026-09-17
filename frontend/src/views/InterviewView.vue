<template>
  <div style="display:flex;flex-direction:column;height:100vh;background:var(--bg-100);">
    <div style="background:var(--surface);border-bottom:1px solid var(--border-default);padding:0 20px;height:52px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;">
      <div style="display:flex;align-items:center;gap:12px;width:200px;">
        <button @click="handleExit" class="iv-exit-btn"><DSIcon name="arrow-left" :size="14" />退出</button>
        <span style="font-size:15px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text-primary);">{{ roleTitle }}</span>
      </div>
      <div style="flex:1;max-width:360px;text-align:center;">
        <span style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">第 {{ questionNum }}/{{ totalCount }} 题</span>
        <div class="ds-progress"><div class="ds-progress-fill" :style="{width:progressPercent+'%'}"></div></div>
      </div>
      <div style="width:200px;text-align:right;display:flex;align-items:center;justify-content:flex-end;gap:10px;">
        <button @click="toggleTts" class="iv-tts-btn" :class="{ on: ttsEnabled }" :title="ttsEnabled?'关闭语音朗读':'开启语音朗读'">
          <DSIcon :name="ttsEnabled ? 'volume-2' : 'volume-x'" :size="15" />
          <span style="font-size:11px;">{{ ttsEnabled ? '语音' : '静音' }}</span>
        </button>
        <span style="font-family:var(--font-mono);font-size:14px;font-weight:600;color:var(--text-primary);">{{ timerDisplay }}</span>
      </div>
    </div>
    <div style="flex:1;display:flex;overflow:hidden;">
      <div ref="chatRef" style="flex:1;overflow-y:auto;padding:24px 20px;">
        <div v-if="connectionError" class="ds-card" style="padding:12px 16px;margin-bottom:16px;color:var(--error,#dc2626);font-size:13px;">
          {{ connectionError }}
        </div>
        <div v-for="(msg,i) in displayMessages" :key="i" :style="msg.side==='ai'?'display:flex;gap:10px;margin-bottom:16px;':'display:flex;gap:10px;margin-bottom:16px;flex-direction:row-reverse;'">
          <div :style="msg.side==='ai'?'width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0;background:var(--brand-900);color:var(--brand-50);':'width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600;flex-shrink:0;background:var(--bg-200);color:var(--text-secondary);'">{{ msg.side==='ai'?'AI':'我' }}</div>
          <div :class="msg.side==='ai'&&msg.msgType==='reaction'?'reaction-bubble':(msg.side==='ai'&&msg.msgType==='hint'?'hint-bubble':'')" :style="msg.side==='ai'?'max-width:70%;padding:12px 16px;border-radius:12px;font-size:14px;line-height:1.7;background:var(--bg-100);color:var(--text-primary);word-break:break-word;':'max-width:70%;padding:12px 16px;border-radius:12px;font-size:14px;line-height:1.7;background:var(--bg-200);color:var(--text-primary);word-break:break-word;'">
            <div v-if="msg.questionId" style="font-family:var(--font-mono);font-size:11px;line-height:1.4;color:var(--text-faint);margin-bottom:4px;">
              题目 ID：{{ msg.questionId }}
            </div>
            {{ msg.displayText }}
            <span v-if="msg.streaming" style="color:var(--brand-600);animation:blink 0.8s infinite;">|</span>
            <!-- TTS 朗读中指示器：仅在最后一条 AI 消息且 TTS 正在朗读时显示 -->
            <span v-if="msg.side==='ai' && ttsSpeaking && i===lastAiIndex && !msg.streaming" class="tts-indicator" title="AI 正在朗读">
              <DSIcon name="volume-2" :size="13" />
            </span>
          </div>
        </div>
        <!-- AI 思考中 loading (首字未到达前只显示这一条, 不再与空内容气泡重复) -->
        <div v-if="showThinking" style="display:flex;gap:10px;margin-bottom:16px;">
          <div style="width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0;background:var(--brand-900);color:var(--brand-50);">AI</div>
          <div style="max-width:70%;padding:12px 16px;border-radius:12px;font-size:14px;line-height:1.7;background:var(--bg-100);color:var(--text-muted);display:flex;align-items:center;gap:8px;">
            <span class="loading-spinner"></span>
            <span>AI 正在思考…</span>
          </div>
        </div>
        <!-- 报告生成中 loading -->
        <div v-if="isGeneratingReport" style="display:flex;gap:10px;margin-bottom:16px;">
          <div style="width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0;background:var(--brand-900);color:var(--brand-50);">AI</div>
          <div style="max-width:70%;padding:12px 16px;border-radius:12px;font-size:14px;line-height:1.7;background:var(--bg-100);color:var(--text-muted);display:flex;align-items:center;gap:8px;">
            <span class="loading-spinner"></span>
            <span>正在生成面试报告，请稍候…</span>
          </div>
        </div>
        <!-- 面试结束，生成报告按钮 -->
        <div v-if="ended && !isGeneratingReport && !reportData" style="text-align:center;padding:24px;">
          <div class="ds-card" style="display:inline-block;padding:20px 32px;background:var(--bg-100);text-align:center;">
            <div style="font-size:16px;font-weight:600;color:var(--text-primary);margin-bottom:8px;">面试已完成</div>
            <div style="font-size:13px;color:var(--text-muted);margin-bottom:16px;">共回答 {{ answeredCount }} 题，用时 {{ timerDisplay }}</div>
            <button class="ds-btn ds-btn-primary" style="font-size:14px;padding:10px 28px;" @click="generateReport">生成面试报告</button>
          </div>
        </div>
      </div>
      <div class="hide-mobile" style="width:260px;border-left:1px solid var(--border-default);background:var(--surface);padding:20px;overflow-y:auto;flex-shrink:0;">
        <div class="ds-card" style="padding:16px;margin-bottom:16px;">
          <h4 style="font-size:12px;font-weight:600;margin-bottom:12px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.06em;">面试信息</h4>
          <div style="display:flex;justify-content:space-between;font-size:13px;padding:4px 0;color:var(--text-muted);"><span>岗位</span><span style="color:var(--text-primary);">{{ roleTitle }}</span></div>
          <div style="display:flex;justify-content:space-between;font-size:13px;padding:4px 0;color:var(--text-muted);"><span>题量</span><span style="color:var(--text-primary);">{{ totalCount }} 题</span></div>
          <div style="display:flex;justify-content:space-between;font-size:13px;padding:4px 0;color:var(--text-muted);"><span>用时</span><span style="color:var(--text-primary);font-family:var(--font-mono);">{{ timerDisplay }}</span></div>
        </div>
        <div class="ds-card" style="padding:16px;margin-bottom:16px;">
          <h4 style="font-size:12px;font-weight:600;margin-bottom:12px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.06em;">题目状态</h4>
          <div v-for="i in totalCount" :key="i" class="iv-q-item" :class="{ done: i<questionNum, current: i===questionNum }">
            <DSIcon v-if="i<questionNum" name="circle-check" :size="14" />
            <span v-else-if="i===questionNum" class="iv-q-dot current"></span>
            <span v-else class="iv-q-dot"></span>
            <span>第 {{ i }} 题</span>
          </div>
        </div>
        <button v-if="!ended" class="ds-btn ds-btn-danger w-full" style="margin-top:12px;padding:10px;" @click="endInterview" :disabled="inputBusy">提前结束面试</button>

        <div class="ds-card" style="padding:16px;margin-top:16px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <h4 style="font-size:12px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.06em;">面试记录</h4>
            <button @click="refreshRecords" style="background:none;border:none;cursor:pointer;color:var(--text-muted);padding:2px;border-radius:var(--radius-sm);" :title="'刷新'">
              <DSIcon name="refresh" :size="12" />
            </button>
          </div>
          <div v-if="recordsLoading" style="font-size:12px;color:var(--text-muted);text-align:center;padding:12px 0;">加载中…</div>
          <div v-else-if="!records.length" style="font-size:12px;color:var(--text-muted);text-align:center;padding:12px 0;">暂无历史记录</div>
          <div v-else style="display:flex;flex-direction:column;gap:6px;max-height:320px;overflow-y:auto;">
            <div v-for="r in records" :key="r.filename" class="iv-rec-item-wrap">
              <button @click="openRecord(r.filename)" class="iv-rec-item">
                <div class="iv-rec-title">{{ r.role_title || '未知岗位' }}</div>
                <div class="iv-rec-meta">
                  <span>{{ r.difficulty_label || '-' }}</span>
                  <span>·</span>
                  <span>{{ r.total_count || '-' }} 题</span>
                  <span v-if="r.timestamp">·</span>
                  <span v-if="r.timestamp" class="iv-rec-ts">{{ r.timestamp.slice(0,4) }}-{{ r.timestamp.slice(4,6) }}-{{ r.timestamp.slice(6,8) }} {{ r.timestamp.slice(9,11) }}:{{ r.timestamp.slice(11,13) }}</span>
                </div>
              </button>
              <button class="iv-rec-del" title="删除"
                      @click.stop="deleteRecord(r.filename)">
                <DSIcon name="trash-2" :size="13" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-if="!ended" style="background:var(--surface);border-top:1px solid var(--border-default);padding:12px 20px;display:flex;gap:10px;flex-shrink:0;align-items:flex-end;">
      <textarea ref="inputRef" v-model="userInput" class="ds-input iv-answer-input" rows="1"
                :placeholder="inputBusy?'AI 正在处理…':(listening?'正在聆听，请说话…':'输入你的回答，Enter 发送 / Shift+Enter 换行…')"
                spellcheck="false" autocomplete="off" autocorrect="off" autocapitalize="off"
                @keydown="handleInputKeydown" :disabled="inputBusy"></textarea>
      <button v-if="voiceSupported" class="ds-btn iv-voice-btn" :class="{ listening }" @click="toggleVoice" :disabled="inputBusy" :title="listening?'停止语音输入':'语音输入'">
        <DSIcon :name="listening ? 'square' : 'mic'" :size="15" />
      </button>
      <button class="ds-btn iv-hint-btn" @click="sendHint" :disabled="inputBusy||hintCount>=2" :title="hintCount>=2?'每题最多2次提示':`获取提示 (${hintCount}/2)`">
        <DSIcon name="lightbulb" :size="15" />{{ hintCount > 0 ? ` ${hintCount}` : '' }}
      </button>
      <button class="ds-btn ds-btn-primary" style="padding:10px 20px;" @click="sendAnswer" :disabled="!userInput.trim()||inputBusy">
        <span v-if="inputBusy" class="loading-spinner" style="width:14px;height:14px;border-width:2px;"></span>
        <span v-else>发送</span>
      </button>
    </div>

    <!-- 记录抽屉 -->
    <div v-if="recordDrawerOpen" class="iv-drawer-mask" @click="closeRecordDrawer"></div>
    <transition name="iv-drawer">
      <div v-if="recordDrawerOpen" class="iv-drawer">
        <div class="iv-drawer-head">
          <div style="min-width:0;">
            <div style="font-size:14px;font-weight:600;color:var(--text-primary);">面试记录</div>
            <div style="font-size:12px;color:var(--text-muted);font-family:var(--font-mono);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{{ recordDrawerTitle }}</div>
          </div>
          <button @click="closeRecordDrawer" style="background:none;border:none;cursor:pointer;color:var(--text-muted);padding:4px;border-radius:var(--radius-sm);"><DSIcon name="x" :size="18" /></button>
        </div>
        <div class="iv-drawer-body">
          <pre class="iv-md-body">{{ recordDrawerContent }}</pre>
        </div>
      </div>
    </transition>
  </div>
</template>
<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useWebSocket } from '../composables/useWebSocket'
import { listInterviewRecords, getInterviewRecord, deleteInterviewRecord } from '../api'
import DSIcon from '../components/DSIcon.vue'
const router = useRouter()
const {
  messages,
  connectionError,
  isStreaming,
  ttsEnabled,
  ttsSpeaking,
  connect,
  sendConfig,
  sendAnswer: wsSendAnswer,
  sendEnd,
  requestReport,
  requestHint,
  close,
  toggleTts,
  stopTts,
} = useWebSocket()
const chatRef = ref(null)
const userInput = ref('')
const inputRef = ref(null)

// 回答输入框: 自适应高度 (1 行起步, 最高 120px 内部滚动)
function autoResizeInput() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}
// Enter 发送, Shift+Enter 换行; isComposing 时(中文输入法组词中)不触发发送
function handleInputKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    sendAnswer()
  }
}
watch(userInput, () => nextTick(autoResizeInput))

// ---- 语音输入 (Web Speech API, 仅 Chrome/Edge 支持, 不支持则隐藏按钮) ----
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
const voiceSupported = !!SpeechRecognition
const listening = ref(false)
let recognizer = null
let voiceBaseText = ''   // 开始识别前输入框已有的文字, 识别结果拼接在其后

function toggleVoice() {
  if (!voiceSupported) return
  if (listening.value) {
    try { recognizer && recognizer.stop() } catch (_) {}
    return
  }
  // 开始语音输入时停止 TTS 朗读, 避免麦克风拾取 AI 声音产生回声
  stopTts()
  recognizer = new SpeechRecognition()
  recognizer.lang = 'zh-CN'
  recognizer.continuous = true
  recognizer.interimResults = true
  voiceBaseText = userInput.value
  let finalText = ''
  recognizer.onresult = (event) => {
    let interim = ''
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const r = event.results[i]
      if (r.isFinal) finalText += r[0].transcript
      else interim += r[0].transcript
    }
    // interim 实时显示; final 累积。拼接在识别前的文字之后
    userInput.value = voiceBaseText + finalText + interim
  }
  recognizer.onerror = () => { listening.value = false }
  recognizer.onend = () => { listening.value = false }
  try {
    recognizer.start()
    listening.value = true
  } catch (_) {
    listening.value = false
  }
}
onUnmounted(() => { try { recognizer && recognizer.stop() } catch (_) {} })

const roleTitle = ref('')
const totalCount = ref(5)
const questionNum = ref(1)
const ended = ref(false)
const reportData = ref('')
const isGeneratingReport = ref(false)
const awaitingResponse = ref(false)
const hintCount = ref(0)  // 当前题目已使用的提示次数
const startTime = ref(Date.now())
const elapsed = ref(0)
let timerInterval = null
onMounted(() => { timerInterval=setInterval(()=>{ if(!ended.value) elapsed.value=Math.floor((Date.now()-startTime.value)/1000) },1000) })
onUnmounted(() => { if(timerInterval) clearInterval(timerInterval) })
const timerDisplay = computed(() => { const m=String(Math.floor(elapsed.value/60)).padStart(2,'0'); const s=String(elapsed.value%60).padStart(2,'0'); return m+':'+s })
const progressPercent = computed(() => Math.min((questionNum.value/totalCount.value)*100,100))
const answeredCount = ref(0)

// 流首字尚未到达时, 不渲染空的流式气泡 (由"AI 正在思考"指示器占位, 避免双气泡)
const liveStreamHasText = computed(() =>
  messages.value.some(m => m.type === 'stream_start' && (m.content || '').trim()))
// 思考中: 等待首字阶段 (含发送后到流开始的空档); 首字到达后让位给流式气泡
const showThinking = computed(() =>
  (isStreaming.value || awaitingResponse.value)
  && !isGeneratingReport.value
  && !liveStreamHasText.value)
const inputBusy = computed(() =>
  (isStreaming.value || awaitingResponse.value) && !isGeneratingReport.value)

// 只显示题目、追问、用户回答、开场/反馈/收尾、提示，不显示报告
const displayMessages = computed(() => messages.value.filter(m => {
  if (m.type === 'report') return false
  if (m.type === 'stream_start' && m.streamType === 'report') return false
  // 空的流式起始帧不显示气泡, 等第一个 chunk 到达再出现
  if (m.type === 'stream_start' && !(m.content || '').trim()) return false
  return ['opening','question','reaction','followup','closing','stream_start','user_answer','status','error','hint'].includes(m.type)
}).map(m => {
  if(m.type==='user_answer') return {side:'user',displayText:m.content,msgType:'user_answer'}
  if(m.type==='status') return {side:'ai',displayText:m.content,msgType:'status'}
  if(m.type==='error') return {side:'ai',displayText:`错误：${m.content}`,msgType:'error'}
  if(m.type==='hint') return {side:'ai',displayText:`提示${m.hintLevel?` (${m.hintLevel}/2)`:''}：${m.content}`,msgType:'hint'}
  return {side:'ai',displayText:m.content||m.full||'',streaming:m.type==='stream_start',msgType:m.type,questionId:m.questionId||''}
}))

// 最后一条 AI 消息的索引（用于 TTS 朗读指示器定位）
const lastAiIndex = computed(() => {
  const msgs = displayMessages.value
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].side === 'ai') return i
  }
  return -1
})

watch(messages, async () => {
  await nextTick()
  if(chatRef.value) chatRef.value.scrollTop=chatRef.value.scrollHeight

  for(let i=0;i<messages.value.length;i++){
    const m=messages.value[i]
    if(m.type==='stream_start' && ['question','followup','closing'].includes(m.streamType)){
      awaitingResponse.value=false
      if(m.streamType==='question' && m.questionIndex){
        questionNum.value=m.questionIndex
        if(m.totalCount) totalCount.value=m.totalCount
        hintCount.value=0  // 新题目重置提示计数
      }
    }
    if(m.type==='question' && m.questionIndex && !m._questionHandled){
      m._questionHandled=true
      questionNum.value=m.questionIndex
      hintCount.value=0  // 新题目重置提示计数
    }
    if(m.type==='interview_ended' && !m._endHandled){
      m._endHandled=true
      ended.value=true
      awaitingResponse.value=false
      answeredCount.value=Number(m.answeredCount||0)
      if(m.totalCount) totalCount.value=Number(m.totalCount)
    }
    if(m.type==='report_ready' && m.reportId && !m._reportHandled){
      m._reportHandled=true
      reportData.value=m.content||''
      isGeneratingReport.value=false
      sessionStorage.setItem('reportData', reportData.value)
      sessionStorage.setItem('reportId', m.reportId)
      sessionStorage.setItem('roleTitle', roleTitle.value)
      sessionStorage.setItem('answeredCount', String(answeredCount.value))
      sessionStorage.setItem('totalCount', String(totalCount.value))
      sessionStorage.setItem('elapsedTime', timerDisplay.value)
      router.push({name:'Summary',params:{reportId:m.reportId}})
      return
    }
    if(m.type==='error' && !m._errorHandled){
      m._errorHandled=true
      awaitingResponse.value=false
      isGeneratingReport.value=false
    }
  }
}, {deep:true})

onMounted(async () => {
  // 优先本次会话选择(可能带简历上下文); 刷新/重进时回退到本地保存的上次配置
  let d = null
  const s = sessionStorage.getItem('selectedRole')
  if (s) { try { d = JSON.parse(s) } catch (_) { d = null } }
  if (!d) {
    const saved = localStorage.getItem('interviewConfig')
    if (saved) { try { d = JSON.parse(saved) } catch (_) { d = null } }
  }
  if (!d || !d.key) { router.push('/choose-job'); return }
  roleTitle.value=d.title||'模拟面试'
  totalCount.value=d.questionCount||5
  try {
    await connect(10000)
    awaitingResponse.value=true
    sendConfig(d.key,d.questionCount||5,2,d.resumeContext||'',d.resumeSkills||[])
  } catch (_) {
    awaitingResponse.value=false
  }
})
onUnmounted(() => close())

function sendAnswer() {
  if(!userInput.value.trim()||inputBusy.value)return
  const t=userInput.value.trim()
  userInput.value=''
  messages.value.push({type:'user_answer',content:t})
  nextTick(autoResizeInput)
  if(wsSendAnswer(t)) awaitingResponse.value=true
}

function sendHint() {
  if(inputBusy.value||hintCount.value>=2)return
  if(requestHint()) {
    hintCount.value++
  }
}

function endInterview() {
  if(confirm('确定要提前结束面试吗？')) {
    userInput.value=''
    if(sendEnd()) awaitingResponse.value=true
  }
}

function generateReport() {
  if(isGeneratingReport.value)return
  if(requestReport()) isGeneratingReport.value=true
}

function handleExit() {
  if(confirm('确定要退出面试吗？')){
    close()
    router.push('/')
  }
}

// ---- 右侧边栏: 历史面试记录 ----
const records = ref([])
const recordsLoading = ref(false)
const recordsPanelOpen = ref(true)
const recordDrawerOpen = ref(false)
const recordDrawerContent = ref('')
const recordDrawerTitle = ref('')

async function refreshRecords() {
  recordsLoading.value = true
  try {
    const r = await listInterviewRecords()
    if (r.success) records.value = r.records || []
  } finally {
    recordsLoading.value = false
  }
}

async function openRecord(fn) {
  recordDrawerTitle.value = fn
  recordDrawerContent.value = '加载中…'
  recordDrawerOpen.value = true
  const r = await getInterviewRecord(fn)
  if (r.success) recordDrawerContent.value = r.content
  else recordDrawerContent.value = `加载失败: ${r.message}`
}

function closeRecordDrawer() {
  recordDrawerOpen.value = false
  recordDrawerContent.value = ''
  recordDrawerTitle.value = ''
}

async function deleteRecord(fn) {
  if (!confirm(`确定删除这条记录吗？`)) return
  const r = await deleteInterviewRecord(fn)
  if (r.success) {
    if (recordDrawerTitle.value === fn) closeRecordDrawer()
    await refreshRecords()
  } else {
    alert(`删除失败: ${r.message}`)
  }
}

onMounted(() => { refreshRecords() })
</script>
<style scoped>
@keyframes blink { 0%,100%{opacity:1;} 50%{opacity:0;} }
.loading-spinner { display:inline-block; width:16px; height:16px; border:2px solid var(--border-default); border-top-color:var(--brand-900); border-radius:50%; animation:spin 0.8s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }

.iv-exit-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: var(--text-muted);
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: var(--radius-sm);
  transition: background var(--dur-fast) ease, color var(--dur-fast) ease;
}
.iv-exit-btn:hover { background: var(--surface-raised); color: var(--text-primary); }

.iv-tts-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: none;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  padding: 4px 9px;
  cursor: pointer;
  color: var(--text-primary);
  opacity: 0.55;
  transition: all 0.2s ease;
}
.iv-tts-btn.on { opacity: 1; border-color: var(--brand-600); background: var(--brand-50); color: var(--brand-800); }

.iv-q-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  padding: 3px 0;
  color: var(--text-faint);
}
.iv-q-item.done { color: var(--success); }
.iv-q-item.current { color: var(--brand-900); font-weight: 600; }
.iv-q-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1.5px solid var(--border-strong);
  box-sizing: border-box;
  flex-shrink: 0;
}
.iv-q-dot.current {
  border-color: var(--brand-700);
  background: var(--brand-600);
  box-shadow: 0 0 0 3px var(--brand-100);
}

.iv-voice-btn { padding: 10px 16px; display: inline-flex; align-items: center; }
.iv-voice-btn.listening { background: var(--error); color: #fff; border-color: var(--error); }

/* 回答输入框: 多行自适应, 取代原单行 input (长回答不再横向溢出) */
.iv-answer-input {
  flex: 1;
  resize: none;
  min-height: 40px;
  max-height: 120px;
  padding: 8px 14px;
  line-height: 1.6;
  font-family: inherit;
  overflow-y: auto;
  box-sizing: border-box;
}
.iv-hint-btn {
  padding: 10px 16px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--accent-700, #b45309);
}

.reaction-bubble { background: var(--surface) !important; border-left: 3px solid var(--brand-400) !important; font-style: italic; }
/* 提示消息样式: 浅黄背景 + 虚线边框 */
.hint-bubble {
  background: #fffbeb !important;
  border: 1px dashed #f59e0b !important;
  border-left: 3px solid #f59e0b !important;
  font-size: 13px !important;
  color: #92400e !important;
}
/* TTS 朗读指示器：小喇叭 + 脉冲动画 */
.tts-indicator {
  display: inline-block;
  margin-left: 6px;
  font-size: 12px;
  animation: tts-pulse 1.2s ease-in-out infinite;
  vertical-align: middle;
}
@keyframes tts-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.2); }
}

/* 历史记录按钮 */
.iv-rec-item-wrap {
  display: flex;
  align-items: stretch;
  gap: 4px;
}
.iv-rec-item {
  flex: 1;
  text-align: left;
  background: var(--bg-100);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  cursor: pointer;
  transition: all 0.18s ease;
  font-family: inherit;
}
.iv-rec-item:hover {
  background: var(--surface-raised);
  border-color: var(--brand-400);
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
.iv-rec-del {
  background: none;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  cursor: pointer;
  padding: 0 8px;
  color: var(--text-faint);
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.18s ease, color 0.18s ease, background 0.18s ease;
}
.iv-rec-item-wrap:hover .iv-rec-del { opacity: 1; }
.iv-rec-del:hover { color: var(--error); background: var(--error-bg); border-color: var(--error); }
.iv-rec-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.iv-rec-meta {
  display: flex;
  gap: 5px;
  font-size: 11px;
  color: var(--text-muted);
  align-items: center;
}
.iv-rec-ts { color: var(--text-faint); font-family: var(--font-mono); }

/* 抽屉 */
.iv-drawer-mask {
  position: fixed;
  inset: 0;
  background: rgba(15,23,42,0.35);
  z-index: 100;
  backdrop-filter: blur(1px);
}
.iv-drawer {
  position: fixed;
  top: 0; right: 0; bottom: 0;
  width: min(560px, 90vw);
  background: var(--surface);
  z-index: 101;
  box-shadow: -8px 0 32px rgba(0,0,0,0.12);
  display: flex;
  flex-direction: column;
}
.iv-drawer-head {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-default);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-shrink: 0;
}
.iv-drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}
.iv-md-body {
  margin: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}
.iv-drawer-enter-active, .iv-drawer-leave-active { transition: transform 0.25s ease; }
.iv-drawer-enter-from, .iv-drawer-leave-to { transform: translateX(100%); }
</style>
