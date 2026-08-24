<template>
  <div style="display:flex;flex-direction:column;height:100vh;background:var(--bg-100);">
    <div style="background:var(--surface);border-bottom:1px solid var(--border-default);padding:0 20px;height:52px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;">
      <div style="display:flex;align-items:center;gap:12px;width:200px;">
        <button @click="handleExit" style="font-size:13px;color:var(--text-muted);background:none;border:none;">← 退出</button>
        <span style="font-size:15px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text-primary);">{{ roleTitle }}</span>
      </div>
      <div style="flex:1;max-width:360px;text-align:center;">
        <span style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">第 {{ questionNum }}/{{ totalCount }} 题</span>
        <div class="ds-progress"><div class="ds-progress-fill" :style="{width:progressPercent+'%'}"></div></div>
      </div>
      <div style="width:200px;text-align:right;display:flex;align-items:center;justify-content:flex-end;gap:10px;">
        <button @click="toggleTts" :title="ttsEnabled?'关闭语音朗读':'开启语音朗读'" style="background:none;border:1px solid var(--border-default);border-radius:6px;padding:4px 8px;font-size:14px;cursor:pointer;color:var(--text-primary);display:flex;align-items:center;gap:4px;transition:all 0.2s;" :style="ttsEnabled?'border-color:var(--brand-600);background:var(--brand-50,#f0f4ff);':'opacity:0.5;'">
          <span style="font-size:15px;">{{ ttsSpeaking ? '🔊' : (ttsEnabled ? '🔈' : '🔇') }}</span>
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
              🔊
            </span>
          </div>
        </div>
        <!-- AI 思考中 loading -->
        <div v-if="isThinking" style="display:flex;gap:10px;margin-bottom:16px;">
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
          <div v-for="i in totalCount" :key="i" style="display:flex;align-items:center;gap:8px;font-size:13px;padding:3px 0;" :style="i<questionNum?'color:var(--success);':(i===questionNum?'color:var(--brand-900);font-weight:600;':'color:var(--text-faint);')">
            <span style="font-size:11px;">{{ i<questionNum?'✓':(i===questionNum?'●':'○') }}</span>
            <span>第 {{ i }} 题</span>
          </div>
        </div>
        <button v-if="!ended" class="ds-btn ds-btn-danger w-full" style="margin-top:12px;padding:10px;" @click="endInterview" :disabled="inputBusy">提前结束面试</button>
      </div>
    </div>
    <div v-if="!ended" style="background:var(--surface);border-top:1px solid var(--border-default);padding:12px 20px;display:flex;gap:10px;flex-shrink:0;">
      <input v-model="userInput" type="text" :placeholder="inputBusy?'AI 正在处理…':(listening?'正在聆听，请说话…':'输入你的回答...')" class="ds-input" style="flex:1;" @keyup.enter="sendAnswer" :disabled="inputBusy" />
      <button v-if="voiceSupported" class="ds-btn" :style="listening?'padding:10px 16px;background:var(--error,#dc2626);color:#fff;':'padding:10px 16px;'" @click="toggleVoice" :disabled="inputBusy" :title="listening?'停止语音输入':'语音输入'">
        {{ listening ? '■' : '🎤' }}
      </button>
      <button class="ds-btn" style="padding:10px 16px;" @click="sendHint" :disabled="inputBusy||hintCount>=2" :title="hintCount>=2?'每题最多2次提示':`获取提示 (${hintCount}/2)`">
        💡{{ hintCount > 0 ? ` ${hintCount}` : '' }}
      </button>
      <button class="ds-btn ds-btn-primary" style="padding:10px 20px;" @click="sendAnswer" :disabled="!userInput.trim()||inputBusy">
        <span v-if="inputBusy" class="loading-spinner" style="width:14px;height:14px;border-width:2px;"></span>
        <span v-else>发送</span>
      </button>
    </div>
  </div>
</template>
<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useWebSocket } from '../composables/useWebSocket'
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

const isThinking = computed(() => isStreaming.value && !isGeneratingReport.value)
const inputBusy = computed(() => isThinking.value || awaitingResponse.value)

// 只显示题目、追问、用户回答、开场/反馈/收尾、提示，不显示报告
const displayMessages = computed(() => messages.value.filter(m => {
  if (m.type === 'report') return false
  if (m.type === 'stream_start' && m.streamType === 'report') return false
  return ['opening','question','reaction','followup','closing','stream_start','user_answer','status','error','hint'].includes(m.type)
}).map(m => {
  if(m.type==='user_answer') return {side:'user',displayText:m.content,msgType:'user_answer'}
  if(m.type==='status') return {side:'ai',displayText:m.content,msgType:'status'}
  if(m.type==='error') return {side:'ai',displayText:`错误：${m.content}`,msgType:'error'}
  if(m.type==='hint') return {side:'ai',displayText:`💡 提示${m.hintLevel?` (${m.hintLevel}/2)`:''}：${m.content}`,msgType:'hint'}
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
  const s=sessionStorage.getItem('selectedRole')
  if(!s){router.push('/choose-job');return}
  let d
  try { d=JSON.parse(s) } catch (_) { router.push('/choose-job');return }
  roleTitle.value=d.title||'模拟面试'
  totalCount.value=d.questionCount||5
  try {
    await connect(10000)
    awaitingResponse.value=true
    sendConfig(d.key,d.questionCount||5,2,d.resumeContext,d.resumeSkills)
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
</script>
<style scoped>
@keyframes blink { 0%,100%{opacity:1;} 50%{opacity:0;} }
.loading-spinner { display:inline-block; width:16px; height:16px; border:2px solid var(--border-default); border-top-color:var(--brand-900); border-radius:50%; animation:spin 0.8s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }
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
</style>
