import { ref, computed, onUnmounted, reactive } from 'vue'

export function useWebSocket() {
  const ws = ref(null)
  const connected = ref(false)
  const messages = ref([])
  const connectionError = ref('')
  const streaming = ref(false)
  const threadId = ref('')
  let activeStream = null

  function connect(timeoutMs = 10000) {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      return Promise.resolve()
    }
    connectionError.value = ''
    return new Promise((resolve, reject) => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const socket = new WebSocket(`${protocol}//${window.location.host}/ws/chat`)
      ws.value = socket
      let settled = false
      const timer = window.setTimeout(() => {
        if (settled) return
        settled = true
        connectionError.value = '连接面试服务超时，请确认后端已启动'
        socket.close()
        reject(new Error(connectionError.value))
      }, timeoutMs)

      socket.onopen = () => {
        window.clearTimeout(timer)
        connected.value = true
        if (!settled) {
          settled = true
          resolve()
        }
      }
      socket.onclose = () => {
        window.clearTimeout(timer)
        connected.value = false
        streaming.value = false
        activeStream = null
        if (!settled) {
          settled = true
          connectionError.value = '无法连接面试服务，请确认后端已启动'
          reject(new Error(connectionError.value))
        }
      }
      socket.onerror = () => {
        connectionError.value = '面试服务连接异常'
      }
      socket.onmessage = (event) => {
        let data
        try {
          data = JSON.parse(event.data)
        } catch (_) {
          messages.value.push({ type: 'error', content: '收到无法解析的服务端消息' })
          return
        }

        if (data.type === 'stream_start') {
          activeStream = reactive({
            type: 'stream_start',
            streamType: data.stream_type,
            content: '',
            full: '',
            questionId: data.question_id || '',
            questionIndex: data.question_index || 0,
            totalCount: data.total_count || 0,
          })
          messages.value.push(activeStream)
          streaming.value = true
        } else if (data.type === 'stream_chunk') {
          if (activeStream) {
            activeStream.content += data.content || ''
            activeStream.full = activeStream.content
          }
        } else if (data.type === 'stream_end') {
          if (activeStream) {
            activeStream.type = data.stream_type || activeStream.streamType
            activeStream.full = data.full_text ?? activeStream.content
            activeStream.content = activeStream.full
            activeStream.reportId = data.report_id || ''
          }
          activeStream = null
          streaming.value = false
        } else if (data.type === 'config_ok') {
          threadId.value = data.thread_id || ''
          messages.value.push({ type: 'config_ok', data })
        } else if (data.type === 'decision') {
          messages.value.push({ type: 'decision', data })
        } else if (data.type === 'interview_ended') {
          messages.value.push({
            type: 'interview_ended',
            content: data.content,
            canReport: data.can_report,
            answeredCount: data.answered_count ?? 0,
            totalCount: data.total_count ?? 0,
          })
        } else if (data.type === 'report_ready') {
          messages.value.push({
            type: 'report_ready',
            reportId: data.report_id,
            content: data.content || '',
          })
        } else if (data.type === 'status') {
          messages.value.push({ type: 'status', content: data.content })
        } else if (data.type === 'error') {
          streaming.value = false
          activeStream = null
          messages.value.push({ type: 'error', content: data.content })
        }
      }
    })
  }

  function send(data) {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) return false
    ws.value.send(JSON.stringify(data))
    return true
  }

  function sendConfig(role, questionCount, difficulty, resumeContext, resumeSkills) {
    return send({
      type: 'config',
      role,
      question_count: questionCount,
      difficulty,
      resume_context: resumeContext || '',
      resume_skills: resumeSkills || [],
    })
  }
  function sendAnswer(content) { return send({ type: 'answer', content }) }
  function sendEnd() { return send({ type: 'end' }) }
  function requestReport() { return send({ type: 'report' }) }
  function close() {
    if (ws.value) ws.value.close()
    ws.value = null
  }
  function clearMessages() { messages.value = [] }

  const isStreaming = computed(() => streaming.value)
  onUnmounted(close)
  return {
    ws,
    connected,
    connectionError,
    threadId,
    messages,
    isStreaming,
    connect,
    send,
    sendConfig,
    sendAnswer,
    sendEnd,
    requestReport,
    close,
    clearMessages,
  }
}
