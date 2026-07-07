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
      <div style="width:200px;text-align:right;">
        <span style="font-family:var(--font-mono);font-size:14px;font-weight:600;color:var(--text-primary);">{{ timerDisplay }}</span>
      </div>
    </div>
    <div style="flex:1;display:flex;overflow:hidden;">
      <div ref="chatRef" style="flex:1;overflow-y:auto;padding:24px 20px;">
        <div v-for="(msg,i) in displayMessages" :key="i" :style="msg.side==='ai'?'display:flex;gap:10px;margin-bottom:16px;':'display:flex;gap:10px;margin-bottom:16px;flex-direction:row-reverse;'">
          <div :style="msg.side==='ai'?'width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0;background:var(--brand-900);color:var(--brand-50);':'width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600;flex-shrink:0;background:var(--bg-200);color:var(--text-secondary);'">{{ msg.side==='ai'?'AI':'我' }}</div>
          <div :style="msg.side==='ai'?'max-width:70%;padding:12px 16px;border-radius:12px;font-size:14px;line-height:1.7;background:var(--bg-100);color:var(--text-primary);word-break:break-word;':'max-width:70%;padding:12px 16px;border-radius:12px;font-size:14px;line-height:1.7;background:var(--bg-200);color:var(--text-primary);word-break:break-word;'">
            {{ msg.displayText }}
            <span v-if="msg.streaming" style="color:var(--brand-600);animation:blink 0.8s infinite;">|</span>
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
        <button v-if="!ended" class="ds-btn ds-btn-danger w-full" style="margin-top:12px;padding:10px;" @click="endInterview">提前结束面试</button>
      </div>
    </div>
    <div v-if="!ended" style="background:var(--surface);border-top:1px solid var(--border-default);padding:12px 20px;display:flex;gap:10px;flex-shrink:0;">
      <input v-model="userInput" type="text" :placeholder="isThinking?'AI 正在思考…':'输入你的回答...'" class="ds-input" style="flex:1;" @keyup.enter="sendAnswer" :disabled="isThinking" />
      <button class="ds-btn ds-btn-primary" style="padding:10px 20px;" @click="sendAnswer" :disabled="!userInput.trim()||isThinking">
        <span v-if="isThinking" class="loading-spinner" style="width:14px;height:14px;border-width:2px;"></span>
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
const { connected, messages, connect, sendConfig, sendAnswer: wsSendAnswer, requestReport, close } = useWebSocket()
const chatRef = ref(null)
const userInput = ref('')
const roleTitle = ref('')
const totalCount = ref(5)
const questionNum = ref(1)
const ended = ref(false)
const reportData = ref('')
const isGeneratingReport = ref(false)
const startTime = ref(Date.now())
const elapsed = ref(0)
let timerInterval = null
onMounted(() => { timerInterval=setInterval(()=>{ if(!ended.value) elapsed.value=Math.floor((Date.now()-startTime.value)/1000) },1000) })
onUnmounted(() => { if(timerInterval) clearInterval(timerInterval) })
const timerDisplay = computed(() => { const m=String(Math.floor(elapsed.value/60)).padStart(2,'0'); const s=String(elapsed.value%60).padStart(2,'0'); return m+':'+s })
const progressPercent = computed(() => Math.min((questionNum.value/totalCount.value)*100,100))
const answeredCount = computed(() => Math.min(questionNum.value, totalCount.value))

// 判断是否正在流式输出题目或追问（不包含报告）
const isThinking = computed(() => {
  const last = messages.value[messages.value.length - 1]
  return last?.type === 'stream_start' && last.streamType !== 'report'
})

// 只显示题目、追问、用户回答，不显示报告
const displayMessages = computed(() => messages.value.filter(m => {
  if (m.type === 'report') return false
  if (m.type === 'stream_start' && m.streamType === 'report') return false
  return ['question','followup','stream_start','user_answer','status'].includes(m.type)
}).map(m => {
  if(m.type==='user_answer') return {side:'user',displayText:m.content}
  if(m.type==='status') return {side:'ai',displayText:m.content}
  return {side:'ai',displayText:m.content||m.full||'',streaming:m.type==='stream_start'}
}))

watch(messages, async () => {
  await nextTick()
  if(chatRef.value) chatRef.value.scrollTop=chatRef.value.scrollHeight

  for(let i=messages.value.length-1;i>=0;i--){
    const m=messages.value[i]
    // 题目计数
    if(m.type==='question'&&!m._counted){
      m._counted=true
      if(questionNum.value<totalCount.value) questionNum.value++
    }
    // 面试结束
    if(m.type==='interview_ended'){
      ended.value=true
    }
    // 报告生成完成 → 自动跳转
    if(m.type==='report' && m.full && isGeneratingReport.value){
      reportData.value=m.full
      isGeneratingReport.value=false
      // 自动跳转到总结页面
      sessionStorage.setItem('reportData', reportData.value)
      sessionStorage.setItem('roleTitle', roleTitle.value)
      sessionStorage.setItem('answeredCount', String(answeredCount.value))
      sessionStorage.setItem('totalCount', String(totalCount.value))
      sessionStorage.setItem('elapsedTime', timerDisplay.value)
      router.push('/summary')
      return
    }
  }
}, {deep:true})

onMounted(() => {
  const s=sessionStorage.getItem('selectedRole')
  if(!s){router.push('/choose-job');return}
  const d=JSON.parse(s)
  roleTitle.value=d.title||'模拟面试'
  connect()
  const check=setInterval(()=>{
    if(connected.value){
      clearInterval(check)
      sendConfig(d.key,5,2,d.resumeContext,d.resumeSkills)
    }
  },200)
})
onUnmounted(() => close())

function sendAnswer() {
  if(!userInput.value.trim()||isThinking.value)return
  const t=userInput.value.trim()
  userInput.value=''
  messages.value.push({type:'user_answer',content:t})
  wsSendAnswer(t)
}

function endInterview() {
  if(confirm('确定要提前结束面试吗？')) {
    ended.value=true
    // 清空输入
    userInput.value=''
  }
}

function generateReport() {
  isGeneratingReport.value=true
  requestReport()
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
</style>
