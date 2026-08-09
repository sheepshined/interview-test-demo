import { ref, computed, onUnmounted } from 'vue'

export function useWebSocket() {
  const ws = ref(null)
  const connected = ref(false)
  const messages = ref([])
  let currentStreamText = ''
  let streamType = ''

  function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    ws.value = new WebSocket(`${protocol}//${host}/ws/chat`)
    ws.value.onopen = () => { connected.value = true }
    ws.value.onclose = () => { connected.value = false }
    ws.value.onerror = (e) => { console.error('WebSocket error:', e) }
    ws.value.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'stream_start') {
        streamType = data.stream_type; currentStreamText = ''
        messages.value.push({ type: 'stream_start', streamType: data.stream_type })
      } else if (data.type === 'stream_chunk') {
        currentStreamText += data.content
        const last = messages.value[messages.value.length - 1]
        if (last && last.type === 'stream_start') { last.content = currentStreamText; last.full = currentStreamText }
      } else if (data.type === 'stream_end') {
        const last = messages.value[messages.value.length - 1]
        if (last) { last.type = streamType; last.full = data.full_text }
        streamType = ''; currentStreamText = ''
      } else if (data.type === 'config_ok') { messages.value.push({ type: 'config_ok', data }) }
      else if (data.type === 'decision') { messages.value.push({ type: 'decision', data }) }
      else if (data.type === 'interview_ended') { messages.value.push({ type: 'interview_ended', content: data.content, can_report: data.can_report }) }
      else if (data.type === 'end') { messages.value.push({ type: 'end', data }) }
      else if (data.type === 'status') { messages.value.push({ type: 'status', content: data.content }) }
      else if (data.type === 'error') { messages.value.push({ type: 'error', content: data.content }) }
    }
  }

  function send(data) { if (ws.value && ws.value.readyState === WebSocket.OPEN) ws.value.send(JSON.stringify(data)) }
  function sendConfig(role, questionCount, difficulty, resumeContext, resumeSkills) { send({ type: 'config', role, question_count: questionCount, difficulty, resume_context: resumeContext || '', resume_skills: resumeSkills || [] }) }
  function sendAnswer(content) { send({ type: 'answer', content }) }
  function requestReport() { send({ type: 'report' }) }
  const isStreaming = computed(() => messages.value.some(m => m.type === 'stream_start'))
  function close() { if (ws.value) ws.value.close() }
  function clearMessages() { messages.value = [] }
  onUnmounted(() => close())
  return { ws, connected, messages, isStreaming, connect, send, sendConfig, sendAnswer, requestReport, close, clearMessages }
}
