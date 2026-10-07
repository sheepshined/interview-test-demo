/* ============================================================
   面试间 · 真实 WebSocket 全协议
   config → 流式出题(打字机) → answer → decision(反馈/追问) →
   hint / 语音输入(本地 ASR) / TTS → end → report → summary
   协议与 frontend/src/composables/useWebSocket.js 对齐。
   ============================================================ */
(() => {
  'use strict';
  const IA = window.IA;

  /* ---------- 配置与守卫 ---------- */
  const config = IA.readConfig();
  if (!config || !config.key) {
    toast('请先选择岗位与题量', 'alert');
    setTimeout(() => { location.href = 'choose-job.html'; }, 600);
    return;
  }

  /* ---------- DOM ---------- */
  const $ = (s) => document.querySelector(s);
  const transcriptEl = $('#transcript');
  const innerEl = $('#transcriptInner');
  const textarea = $('#answer');
  const sendBtn = $('#sendBtn');
  const hintBtn = $('#hintBtn');
  const micBtn = $('#micBtn');
  const ttsBtn = $('#ttsBtn');
  const endBtn = $('#endBtn');
  const timerEl = $('#timer');
  const timer2El = $('#timer2');
  const ticksEl = $('#progressTicks');
  const progressLabel = $('#progressLabel');
  const qListEl = $('#qList');
  const kvRole = $('#kvRole');
  const kvCount = $('#kvCount');
  const kvAnswered = $('#kvAnswered');
  const roleTitleEl = $('#roomRole');
  const deskMetaHint = $('#hintMeta');

  /* ---------- 状态 ---------- */
  const state = {
    connected: false, streaming: false, busy: false,
    questionNum: 0, totalCount: config.questionCount || 5,
    hintCount: 0, threadId: '',
    sec: 0, answered: 0, canReport: false,
    ended: false, reportAsked: false,
  };
  roleTitleEl.childNodes[0].textContent = config.title || '模拟面试';
  kvRole.textContent = config.title || '—';
  kvCount.textContent = state.totalCount + ' 题';
  ticksEl.innerHTML = Array.from({ length: state.totalCount }, () => '<i></i>').join('');
  qListEl.innerHTML = Array.from({ length: state.totalCount }, (_, i) =>
    `<li data-q="${i + 1}"><span class="qn">${String(i + 1).padStart(2, '0')}</span><span>待出题</span><span class="state">等待</span></li>`).join('');

  /* ---------- 计时 ---------- */
  setInterval(() => {
    state.sec++;
    const t = String(Math.floor(state.sec / 60)).padStart(2, '0') + ':' + String(state.sec % 60).padStart(2, '0');
    timerEl.textContent = t; timer2El.textContent = t;
  }, 1000);

  /* ---------- TTS ---------- */
  const SPEAKABLE = new Set(['opening', 'question', 'followup', 'closing']);
  let ttsOn = true;
  function speak(text) {
    if (!ttsOn || !window.speechSynthesis || !text || !text.trim()) return;
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = 'zh-CN'; u.rate = 0.92;
      window.speechSynthesis.speak(u);
    } catch (_) {}
  }
  function stopSpeak() { try { window.speechSynthesis && window.speechSynthesis.cancel(); } catch (_) {} }
  ttsBtn.addEventListener('click', () => {
    ttsOn = !ttsOn;
    ttsBtn.classList.toggle('is-on', ttsOn);
    if (!ttsOn) stopSpeak();
    toast(ttsOn ? '语音朗读已开启' : '语音朗读已关闭', 'volume');
  });

  /* ---------- 消息渲染 ---------- */
  const esc = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const now = () => {
    const d = new Date();
    return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
  };
  const scrollDown = () => { transcriptEl.scrollTop = transcriptEl.scrollHeight; };

  function statusLine(text) {
    const el = document.createElement('div');
    el.className = 'msg msg-status';
    el.innerHTML = `<span>— ${esc(text)} —</span>`;
    innerEl.appendChild(el); scrollDown();
    return el;
  }
  function reactionLine(text) {
    const el = document.createElement('article');
    el.className = 'msg msg-comment';
    el.innerHTML = `<div class="msg-head"><span class="msg-who" style="color:var(--ink-3)">面试官 · 反馈</span></div>
      <div class="msg-text">${esc(text)}</div>`;
    innerEl.appendChild(el); scrollDown();
  }
  function userMessage(text) {
    const el = document.createElement('article');
    el.className = 'msg msg-user';
    el.innerHTML = `<div class="msg-head"><span class="msg-who">我</span><span class="msg-time">${now()}</span></div>
      <div class="msg-text">${esc(text)}</div>`;
    innerEl.appendChild(el); scrollDown();
  }
  function hintCard(level, content) {
    const el = document.createElement('article');
    el.className = 'msg msg-hint';
    el.innerHTML = `<div class="msg-head"><span class="msg-who" style="color:var(--ink-3)">提示</span></div>
      <div class="hint-card"><span data-ic="bulb"></span>
      <div class="txt"><b>HINT ${level}/2</b><br />${esc(content)}</div></div>`;
    if (window.renderIcons) renderIcons(el);
    innerEl.appendChild(el); scrollDown();
  }
  function aiMessage({ qid }) {
    const el = document.createElement('article');
    el.className = 'msg msg-ai';
    el.innerHTML = `<div class="msg-head"><span class="msg-who">面试官</span><span class="msg-time">${now()}</span>
      ${qid ? `<span class="msg-qid">${esc(qid)}</span>` : ''}</div>
      <div class="msg-text"><span class="stream-text"></span><span class="caret"></span></div>`;
    innerEl.appendChild(el); scrollDown();
    return { el, textEl: el.querySelector('.stream-text') };
  }

  /* ---------- 打字机（与 Vue 版同策略：积压越多吐越快） ---------- */
  const REVEAL_MS = 24;
  let active = null;   // { el, textEl, content, pending, ended, streamType, qid }
  let revealTimer = null;
  function startStream(meta) {
    flushStream();
    active = { el: null, textEl: null, content: '', pending: '', ended: false, ...meta };
    if (active.streamType !== 'report') {
      const m = aiMessage({ qid: active.qid || '' });
      active.el = m.el; active.textEl = m.textEl;
    }
    state.streaming = true;
    if (!revealTimer) revealTimer = setInterval(revealTick, REVEAL_MS);
  }
  function revealTick() {
    if (!active) { stopReveal(); return; }
    if (!active.pending) {
      if (active.ended) finalizeStream();
      return;
    }
    const n = active.pending.length > 80 ? 6 : active.pending.length > 30 ? 3 : 1;
    active.content += active.pending.slice(0, n);
    active.pending = active.pending.slice(n);
    if (active.textEl) {
      active.textEl.textContent = active.content;
      scrollDown();
    }
  }
  function stopReveal() { if (revealTimer) { clearInterval(revealTimer); revealTimer = null; } }
  function finalizeStream() {
    if (!active) return;
    if (active.textEl) {
      active.textEl.textContent = active.full != null ? active.full : active.content;
      active.el.querySelector('.caret') && active.el.querySelector('.caret').remove();
    }
    const type = active.streamType, content = active.textEl ? (active.full != null ? active.full : active.content) : '';
    active = null;
    state.streaming = false;
    stopReveal();
    if (SPEAKABLE.has(type)) speak(content);
  }
  function flushStream() { if (active) finalizeStream(); }

  /* ---------- 进度同步 ---------- */
  function syncProgress() {
    if (ticksEl.children[state.questionNum - 1]) {
      [...ticksEl.children].forEach((el, i) => {
        el.className = i < state.questionNum - 1 ? 'done' : i === state.questionNum - 1 ? 'now' : '';
      });
    }
    progressLabel.innerHTML = `第 <b>${Math.max(state.questionNum, 1)}</b> / ${state.totalCount} 题 · ${state.ended ? 'Ended' : 'In progress'}`;
    kvAnswered.textContent = state.answered + ' 题';
    [...qListEl.children].forEach((li) => {
      const n = Number(li.dataset.q);
      li.classList.toggle('done', n < state.questionNum);
      li.classList.toggle('now', n === state.questionNum && !state.ended);
      if (n < state.questionNum) li.querySelector('.state').textContent = '已评分';
      else if (n === state.questionNum && !state.ended) li.querySelector('.state').textContent = '作答中';
    });
  }
  function setQuestionMeta(index, total, title) {
    state.questionNum = index || state.questionNum;
    if (total) state.totalCount = total;
    if (index) {
      state.hintCount = 0;
      deskMetaHint.textContent = '提示 0 / 2 已使用';
      const li = qListEl.querySelector(`[data-q="${index}"]`);
      if (li && title) li.children[1].textContent = title;
    }
    syncProgress();
  }

  /* ---------- 视图切换 ---------- */
  function switchView(key) {
    document.querySelectorAll('[data-state-view]').forEach((v) => { v.hidden = v.dataset.stateView !== key; });
  }

  /* ---------- 生成报告 ---------- */
  function askReport() {
    if (state.reportAsked) return;
    state.reportAsked = true;
    switchView('gen');
    ws.send(JSON.stringify({ type: 'report' }));
  }

  /* ---------- WebSocket ---------- */
  let ws = null;
  let wsTimer = null;
  function connect() {
    const token = IA.getToken();
    statusLine('正在连接面试服务');
    ws = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws/chat?token=${encodeURIComponent(token)}`);
    wsTimer = setTimeout(() => {
      if (ws.readyState !== WebSocket.OPEN) {
        toast('连接面试服务超时，请确认后端已启动', 'alert');
        statusLine('连接超时，请刷新重试');
      }
    }, 10000);

    ws.onopen = () => {
      clearTimeout(wsTimer);
      state.connected = true;
      ws.send(JSON.stringify({
        type: 'config',
        role: config.key,
        question_count: state.totalCount,
        difficulty: 2,
        resume_context: config.resumeContext || '',
        resume_skills: config.resumeSkills || [],
      }));
    };
    ws.onclose = () => {
      state.connected = false;
      stopSpeak(); flushStream();
      if (!state.ended) {
        statusLine('连接已断开 · 请刷新页面重试');
        toast('面试服务连接断开', 'alert');
      }
    };
    ws.onmessage = (event) => {
      let data;
      try { data = JSON.parse(event.data); } catch (_) { return; }
      handle(data);
    };
  }

  function handle(data) {
    switch (data.type) {
      case 'config_ok':
        state.threadId = data.thread_id || '';
        statusLine(`面试开始 · ${now()}`);
        break;
      case 'stream_start': {
        const st = data.stream_type;
        const qid = data.question_index ? `Q${data.question_index}${data.total_count ? ' · ' + st : ''}` : '';
        startStream({ streamType: st, qid: data.question_index ? `Q${data.question_index}` : '' });
        if (st === 'question' && data.question_index) {
          setQuestionMeta(data.question_index, data.total_count, '');
        }
        break;
      }
      case 'stream_chunk':
        if (active) {
          if (active.streamType === 'report') return;
          active.pending += data.content || '';
        }
        break;
      case 'stream_end':
        if (active) {
          active.endType = data.stream_type || active.streamType;
          active.full = data.full_text != null ? data.full_text : (active.content + active.pending);
          active.ended = true;
          if (active.streamType === 'report') { active = null; state.streaming = false; stopReveal(); }
        }
        break;
      case 'decision':
        if (data.reason) reactionLine(data.reason);
        break;
      case 'interview_ended':
        state.ended = true;
        state.answered = Number(data.answered_count ?? state.questionNum);
        state.canReport = !!data.can_report;
        flushStream();
        switchView('done');
        $('#doneAnswered').textContent = state.answered;
        $('#doneTotal').textContent = data.total_count ?? state.totalCount;
        $('#doneTime').textContent = timerEl.textContent;
        syncProgress();
        toast('面试已结束，可以生成报告了');
        break;
      case 'report_ready':
        sessionStorage.setItem('reportId', data.report_id || '');
        sessionStorage.setItem('roleTitle', config.title || '');
        sessionStorage.setItem('answeredCount', String(state.answered));
        sessionStorage.setItem('totalCount', String(state.totalCount));
        sessionStorage.setItem('elapsedTime', timerEl.textContent);
        toast('报告已生成，正在打开…');
        setTimeout(() => { IA.go('summary?id=' + encodeURIComponent(data.report_id)); }, 500);
        break;
      case 'hint':
        state.hintCount = Math.max(state.hintCount, data.hint_level || state.hintCount + 1);
        hintCard(data.hint_level || state.hintCount, data.content || '');
        deskMetaHint.textContent = `提示 ${state.hintCount} / 2 已使用`;
        break;
      case 'status':
        if (data.content) statusLine(data.content);
        break;
      case 'error':
        flushStream();
        toast(data.content || '服务端错误', 'alert');
        statusLine(data.content || '服务端错误');
        break;
    }
  }

  /* ---------- 作答台 ---------- */
  function autoHeight() {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
  }
  textarea.addEventListener('input', autoHeight);
  textarea.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendAnswer(); }
  });
  sendBtn.addEventListener('click', sendAnswer);

  function sendAnswer() {
    const v = textarea.value.trim();
    if (!v) { toast('先写下你的回答', 'alert'); return; }
    if (!state.connected) { toast('面试服务未连接', 'alert'); return; }
    if (state.streaming) { toast('面试官正在输入，请稍候', 'alert'); return; }
    userMessage(v);
    textarea.value = ''; autoHeight();
    state.answered = Math.max(state.answered, state.questionNum);
    ws.send(JSON.stringify({ type: 'answer', content: v }));
    statusLine('已提交 · 评分中');
  }

  hintBtn.addEventListener('click', () => {
    if (state.hintCount >= 2) { toast('本题提示已用完（2/2）', 'bulb'); return; }
    if (!state.connected) return;
    ws.send(JSON.stringify({ type: 'hint' }));
    state.hintCount++;
    deskMetaHint.textContent = `提示 ${state.hintCount} / 2 已使用`;
  });

  endBtn.addEventListener('click', () => {
    if (state.ended) { askReport(); return; }
    if (!state.connected) return;
    if (!confirm('确定提前结束本场面试吗？已回答的题目会保留并计入报告。')) return;
    ws.send(JSON.stringify({ type: 'end' }));
    statusLine('正在收尾…');
  });

  /* 完成态里的生成报告按钮 */
  $('#reportBtn').addEventListener('click', askReport);

  /* ---------- 语音输入（本地 ASR） ---------- */
  const voice = window.createVoiceInput({
    onResult: (text) => {
      micBtn.classList.remove('is-live');
      textarea.value = (textarea.value ? textarea.value + ' ' : '') + text;
      autoHeight();
      toast('语音已转写');
    },
    onError: (msg) => { micBtn.classList.remove('is-live'); toast(msg, 'alert'); },
  });
  micBtn.addEventListener('click', async () => {
    if (voice.processing()) return;
    if (voice.recording()) { await voice.stop(); return; }
    stopSpeak(); // 防回声
    const ok = await voice.start();
    if (ok) { micBtn.classList.add('is-live'); toast('正在聆听，请说话…', 'mic'); }
  });

  /* ---------- 历史记录（右侧栏，真实数据） ---------- */
  async function loadRecords() {
    const box = $('#recList');
    const res = await IA.listInterviewRecords();
    if (!res.success) { box.innerHTML = '<div class="rec-item"><div class="t">' + (res.message || '加载失败') + '</div></div>'; return; }
    const records = res.records || [];
    if (!records.length) {
      box.innerHTML = '<div class="rec-item"><div class="t" style="color:var(--ink-4)">暂无历史记录</div></div>';
      return;
    }
    box.innerHTML = records.slice(0, 4).map((r) =>
      `<div class="rec-item"><div style="min-width:0"><div class="t">${esc(r.role_title || r.filename || '面试记录')}</div>
        <div class="d">${esc((r.timestamp || '').replace(/T.*$/, ''))} · ${esc(r.total_count || '?')} 题</div></div>
        <button class="del" title="删除" data-del="${esc(r.filename)}">${window.iconEl('trash')}</button></div>`).join('');
    box.querySelectorAll('[data-del]').forEach((b) => b.addEventListener('click', async () => {
      const r2 = await IA.deleteInterviewRecord(b.dataset.del);
      if (r2.success) { toast('已删除'); loadRecords(); } else toast(r2.message || '删除失败', 'alert');
    }));
  }

  /* ---------- 启动 ---------- */
  if (IA.requireAuth()) {
    syncProgress();
    loadRecords();
    connect();
  }
})();
