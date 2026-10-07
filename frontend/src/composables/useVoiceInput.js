/**
 * useVoiceInput — 本地语音输入 composable (v1.1)
 *
 * 链路: 麦克风 getUserMedia → Web Audio 采集 PCM → 线性重采样 16kHz →
 *       编码 16-bit WAV → POST /api/asr → SenseVoice (后端本地推理) → 文本
 *
 * 替代原 Web Speech API (Chrome 专属 + 音频上云): 现在任意现代浏览器可用、
 * 完全离线。点击开始 → 再次点击结束 (面试回答较长, 按住说话易疲劳)。
 *
 * 用法:
 *   const { supported, recording, processing, error, elapsed, start, stop, dispose }
 *     = useVoiceInput({ onResult: (text) => { ... } })
 */
import { getCurrentInstance, onUnmounted, ref } from 'vue'
import { transcribeAudio } from '../api'

const TARGET_SR = 16000     // 后端 SenseVoice 要求的采样率
const MAX_MS = 120000       // 单次录音上限 (与后端 MAX_DURATION_S 对齐)

export function useVoiceInput({ onResult } = {}) {
  const supported = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)
  const recording = ref(false)   // 正在录音
  const processing = ref(false)  // 正在上传/识别
  const error = ref('')
  const elapsed = ref(0)         // 已录秒数 (显示用)

  let stream = null
  let audioCtx = null
  let source = null
  let processor = null
  let chunks = []
  let startedAt = 0
  let timer = null
  let autoStopTimer = null

  async function start() {
    if (!supported || recording.value || processing.value) return false
    error.value = ''
    try {
      // 回声消除/降噪/自动增益: 面试场景 TTS 念题与说话可能同时发生
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
    } catch (e) {
      error.value = '无法访问麦克风，请检查浏览器权限'
      return false
    }
    audioCtx = new AudioContext()
    source = audioCtx.createMediaStreamSource(stream)
    processor = audioCtx.createScriptProcessor(4096, 1, 1)
    chunks = []
    processor.onaudioprocess = (e) => {
      if (!recording.value) return
      chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)))
    }
    source.connect(processor)
    processor.connect(audioCtx.destination)  // ScriptProcessor 必须连到输出端才会触发回调

    recording.value = true
    startedAt = Date.now()
    elapsed.value = 0
    timer = setInterval(() => {
      elapsed.value = Math.floor((Date.now() - startedAt) / 1000)
    }, 250)
    autoStopTimer = setTimeout(() => stop(), MAX_MS)  // 超时自动收尾
    return true
  }

  async function stop() {
    if (!recording.value) return
    recording.value = false
    clearInterval(timer)
    timer = null
    clearTimeout(autoStopTimer)
    autoStopTimer = null

    // 收尾音频管线 (合并采样块要在 close 之前拿到, 但 Float32Array 已拷贝, 无碍)
    const srcRate = audioCtx ? audioCtx.sampleRate : TARGET_SR
    try { processor && processor.disconnect() } catch (_) {}
    try { source && source.disconnect() } catch (_) {}
    try { stream && stream.getTracks().forEach(t => t.stop()) } catch (_) {}
    try { audioCtx && audioCtx.close() } catch (_) {}
    processor = source = stream = audioCtx = null

    const blob = encodeWav(chunks, srcRate)
    chunks = []
    if (blob.size <= 44) return  // 没采到数据

    processing.value = true
    try {
      const res = await transcribeAudio(blob)
      if (res && res.success) {
        const text = (res.text || '').trim()
        if (text) {
          if (typeof onResult === 'function') onResult(text)
        } else {
          error.value = '未识别到语音内容，请靠近麦克风再试'
        }
      } else {
        error.value = (res && (res.error || res.message)) || '识别失败，请重试'
      }
    } finally {
      processing.value = false
    }
  }

  function encodeWav(chunksArr, srcRate) {
    let total = 0
    for (const c of chunksArr) total += c.length
    const merged = new Float32Array(total)
    let off = 0
    for (const c of chunksArr) { merged.set(c, off); off += c.length }

    // 线性插值重采样到 16kHz (语音识别对插值精度不敏感)
    let samples = merged
    if (srcRate !== TARGET_SR && merged.length > 1) {
      const nOut = Math.round(merged.length / srcRate * TARGET_SR)
      const out = new Float32Array(nOut)
      for (let i = 0; i < nOut; i++) {
        const t = i / TARGET_SR * srcRate
        const i0 = Math.floor(t)
        const i1 = Math.min(i0 + 1, merged.length - 1)
        out[i] = merged[i0] + (merged[i1] - merged[i0]) * (t - i0)
      }
      samples = out
    }

    // 16-bit 单声道 PCM WAV
    const buf = new ArrayBuffer(44 + samples.length * 2)
    const view = new DataView(buf)
    const writeStr = (pos, s) => { for (let i = 0; i < s.length; i++) view.setUint8(pos + i, s.charCodeAt(i)) }
    writeStr(0, 'RIFF'); view.setUint32(4, 36 + samples.length * 2, true); writeStr(8, 'WAVE')
    writeStr(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true)
    view.setUint16(22, 1, true); view.setUint32(24, TARGET_SR, true)
    view.setUint32(28, TARGET_SR * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true)
    writeStr(36, 'data'); view.setUint32(40, samples.length * 2, true)
    let pos = 44
    for (let i = 0; i < samples.length; i++, pos += 2) {
      const s = Math.max(-1, Math.min(1, samples[i]))
      view.setInt16(pos, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    }
    return new Blob([buf], { type: 'audio/wav' })
  }

  function dispose() {
    clearInterval(timer); clearTimeout(autoStopTimer)
    timer = autoStopTimer = null
    try { processor && processor.disconnect() } catch (_) {}
    try { source && source.disconnect() } catch (_) {}
    try { stream && stream.getTracks().forEach(t => t.stop()) } catch (_) {}
    try { audioCtx && audioCtx.close() } catch (_) {}
    processor = source = stream = audioCtx = null
    recording.value = false
  }

  if (getCurrentInstance()) onUnmounted(dispose)

  return { supported, recording, processing, error, elapsed, start, stop, dispose }
}
