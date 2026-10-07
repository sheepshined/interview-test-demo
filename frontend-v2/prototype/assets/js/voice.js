/* ============================================================
   墨卷档案 · 本地语音输入（frontend/src/composables/useVoiceInput 移植）
   麦克风 → PCM 采集 → 线性重采样 16kHz → 16-bit WAV → POST /api/asr
   点击开始 / 再次点击结束；依赖 api.js。
   ============================================================ */
(() => {
  'use strict';

  const TARGET_SR = 16000;
  const MAX_MS = 120000;

  function createVoiceInput({ onResult, onError } = {}) {
    const supported = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    let recording = false, processing = false;
    let stream = null, audioCtx = null, source = null, processor = null;
    let chunks = [], startedAt = 0, timer = null, autoStopTimer = null;

    async function start() {
      if (!supported || recording || processing) return false;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
      } catch (e) {
        onError && onError('无法访问麦克风，请检查浏览器权限');
        return false;
      }
      audioCtx = new AudioContext();
      source = audioCtx.createMediaStreamSource(stream);
      processor = audioCtx.createScriptProcessor(4096, 1, 1);
      chunks = [];
      processor.onaudioprocess = (e) => {
        if (!recording) return;
        chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
      };
      source.connect(processor);
      processor.connect(audioCtx.destination);
      recording = true;
      startedAt = Date.now();
      autoStopTimer = setTimeout(() => stop(), MAX_MS);
      return true;
    }

    async function stop() {
      if (!recording) return;
      recording = false;
      clearTimeout(autoStopTimer); autoStopTimer = null;

      const srcRate = audioCtx ? audioCtx.sampleRate : TARGET_SR;
      try { processor && processor.disconnect(); } catch (_) {}
      try { source && source.disconnect(); } catch (_) {}
      try { stream && stream.getTracks().forEach((t) => t.stop()); } catch (_) {}
      try { audioCtx && audioCtx.close(); } catch (_) {}
      processor = source = stream = audioCtx = null;

      const blob = encodeWav(chunks, srcRate);
      chunks = [];
      if (blob.size <= 44) { onError && onError('没有录到声音'); return; }

      processing = true;
      try {
        const res = await window.IA.transcribeAudio(blob);
        if (res && res.success) {
          const text = (res.text || '').trim();
          if (text) onResult && onResult(text);
          else onError && onError('未识别到语音内容，请靠近麦克风再试');
        } else {
          onError && onError((res && (res.error || res.message)) || '识别失败，请重试');
        }
      } finally {
        processing = false;
      }
    }

    function encodeWav(chunksArr, srcRate) {
      let total = 0;
      for (const c of chunksArr) total += c.length;
      const merged = new Float32Array(total);
      let off = 0;
      for (const c of chunksArr) { merged.set(c, off); off += c.length; }

      let samples = merged;
      if (srcRate !== TARGET_SR && merged.length > 1) {
        const nOut = Math.round(merged.length / srcRate * TARGET_SR);
        const out = new Float32Array(nOut);
        for (let i = 0; i < nOut; i++) {
          const t = i / TARGET_SR * srcRate;
          const i0 = Math.floor(t);
          const i1 = Math.min(i0 + 1, merged.length - 1);
          out[i] = merged[i0] + (merged[i1] - merged[i0]) * (t - i0);
        }
        samples = out;
      }

      const buf = new ArrayBuffer(44 + samples.length * 2);
      const view = new DataView(buf);
      const writeStr = (pos, s) => { for (let i = 0; i < s.length; i++) view.setUint8(pos + i, s.charCodeAt(i)); };
      writeStr(0, 'RIFF'); view.setUint32(4, 36 + samples.length * 2, true); writeStr(8, 'WAVE');
      writeStr(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
      view.setUint16(22, 1, true); view.setUint32(24, TARGET_SR, true);
      view.setUint32(28, TARGET_SR * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
      writeStr(36, 'data'); view.setUint32(40, samples.length * 2, true);
      let pos = 44;
      for (let i = 0; i < samples.length; i++, pos += 2) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(pos, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      }
      return new Blob([buf], { type: 'audio/wav' });
    }

    function dispose() {
      clearTimeout(autoStopTimer); autoStopTimer = null;
      try { processor && processor.disconnect(); } catch (_) {}
      try { source && source.disconnect(); } catch (_) {}
      try { stream && stream.getTracks().forEach((t) => t.stop()); } catch (_) {}
      try { audioCtx && audioCtx.close(); } catch (_) {}
      processor = source = stream = audioCtx = null;
      recording = false;
    }

    return { supported, recording: () => recording, processing: () => processing, start, stop, dispose };
  }

  window.createVoiceInput = createVoiceInput;
})();
