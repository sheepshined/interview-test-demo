/* ============================================================
   知识库 AI 对话 · 真实数据
   会话管理(sessions CRUD) + /kb/qa 检索问答(来源/sparse 提示)
   + 本地语音输入(ASR)
   ============================================================ */
(() => {
  'use strict';
  const IA = window.IA;
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  let sessionId = null;
  let sessions = [];

  /* ---------- 会话时间显示 ---------- */
  function fmtTime(s) {
    const t = String(s || '');
    if (t.length < 10) return t || '';
    const d = new Date(t.replace(' ', 'T'));
    const diff = (Date.now() - d.getTime()) / 3600000;
    if (diff < 1) return '刚刚';
    if (diff < 24) return Math.floor(diff) + ' 小时前';
    if (diff < 48) return '昨天';
    return t.slice(5, 10);
  }

  /* ---------- 会话列表 ---------- */
  async function loadSessions(keepId = true) {
    const res = await IA.kbChatListSessions();
    if (!res.success) {
      $('#sessList').innerHTML = `<div class="mono" style="padding:12px">${esc(res.message || '加载失败')}</div>`;
      return;
    }
    sessions = res.sessions || [];
    $('#sessCount').textContent = 'Conversations · ' + sessions.length;
    $('#sessList').innerHTML = sessions.map((s) =>
      `<button class="sess${s.id === sessionId ? ' is-on' : ''}" data-id="${s.id}">
        <span class="body"><span class="t">${esc(s.title || '新对话')}</span>
        <span class="d">${esc(fmtTime(s.updated_at || s.created_at))} · ${s.message_count != null ? s.message_count + ' 条' : ''}</span></span>
        <span class="del" title="删除" data-del="${s.id}">${window.iconEl('trash')}</span>
      </button>`).join('') || '<div class="mono" style="padding:12px">暂无会话</div>';
    if (window.renderIcons) renderIcons($('#sessList'));
    $('#sessList').querySelectorAll('.sess').forEach((el) => el.addEventListener('click', (e) => {
      if (e.target.closest('[data-del]')) return;
      openSession(Number(el.dataset.id));
    }));
    $('#sessList').querySelectorAll('[data-del]').forEach((el) => el.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!confirm('删除这个会话？')) return;
      const r2 = await IA.kbChatDeleteSession(Number(el.dataset.del));
      if (r2.success) {
        toast('会话已删除');
        if (sessionId === Number(el.dataset.del)) { sessionId = null; $('#chatBody').innerHTML = ''; $('#chatTitle').textContent = '新对话'; }
        loadSessions();
      } else toast(r2.message || '删除失败', 'alert');
    }));
    if (keepId && !sessionId && sessions.length) openSession(sessions[0].id);
  }

  /* ---------- 打开会话 ---------- */
  async function openSession(id) {
    sessionId = id;
    const res = await IA.kbChatGetSession(id);
    if (!res.success) { toast(res.message || '会话加载失败', 'alert'); return; }
    const sess = res.session || {};
    $('#chatTitle').textContent = sess.title || '会话';
    const msgs = res.messages || sess.messages || []; // 后端把 messages 放在顶层键
    const body = $('#chatBody');
    body.innerHTML = '';
    msgs.forEach((m) => {
      if (m.role === 'user') appendUser(m.content);
      else appendAi(m.content, m.sources || [], m.sparse);
    });
    body.scrollTop = body.scrollHeight;
    loadSessions();
  }

  async function newChat() {
    const res = await IA.kbChatCreateSession();
    if (!res.success) { toast(res.message || '创建失败', 'alert'); return; }
    sessionId = res.session.id;
    $('#chatTitle').textContent = res.session.title || '新对话';
    $('#chatBody').innerHTML = `<div class="empty" style="margin:30px 20px"><div class="empty-title">问点什么吧</div>
      <div class="empty-sub">回答仅基于你的知识库，并附带来源</div></div>`;
    loadSessions();
  }

  /* ---------- 消息渲染 ---------- */
  function appendUser(text) {
    const el = document.createElement('div');
    el.className = 'turn turn-user';
    el.innerHTML = `<div class="bubble"><div class="who">我</div>${esc(text)}</div>`;
    $('#chatBody').appendChild(el);
  }

  function sourcesHtml(sources) {
    if (!sources || !sources.length) return '';
    const rows = sources.map((s, i) => {
      let score = Number(s.score || 0);
      if (score <= 1) score = Math.round(score * 100);
      const href = s.note_id ? 'note.html?id=' + encodeURIComponent(s.note_id) : 'workspace.html';
      return `<a class="source-row" href="${href}"><span class="no">${i + 1}</span><span class="name">${esc(s.title || s.source || '来源')}</span>
        <span class="bar"><i style="width:${Math.min(100, score)}%"></i></span><span class="pct">${score}%</span></a>`;
    }).join('');
    return `<div class="sources"><div class="st"><span data-ic="book"></span>参考来源 · ${sources.length}</div>${rows}</div>`;
  }

  function appendAi(mdOrText, sources, sparse) {
    const el = document.createElement('div');
    el.className = 'turn turn-ai';
    const html = window.renderMd(mdOrText || '');
    el.innerHTML = `<div class="who-row"><span class="who">知识库助手</span><span class="time">刚刚</span></div>
      <div class="answer">${html}${sourcesHtml(sources)}
      ${sparse ? '<div class="sparse"><span data-ic="alert"></span><span>相关度不算高，可能需要补充更多资料</span><a href="workspace.html">去导入 →</a></div>' : ''}</div>`;
    $('#chatBody').appendChild(el);
    if (window.renderIcons) renderIcons(el);
    el.querySelectorAll('.wikilink').forEach((w) => w.addEventListener('click', () => {
      IA.go('workspace?q=' + encodeURIComponent(w.dataset.wiki));
    }));
  }

  /* ---------- 提问 ---------- */
  const ta = $('#q');
  let busy = false;
  async function ask() {
    const v = ta.value.trim();
    if (!v) { toast('先输入一个问题', 'alert'); return; }
    if (busy) return;
    busy = true;
    appendUser(v);
    ta.value = ''; ta.style.height = 'auto';
    const body = $('#chatBody');
    const think = document.createElement('div');
    think.className = 'turn turn-ai';
    think.innerHTML = `<div class="who-row"><span class="who">知识库助手</span><span class="time">检索中…</span></div>
      <div class="thinking"><i></i><i></i><i></i></div>`;
    body.appendChild(think);
    body.scrollTop = body.scrollHeight;

    const res = await IA.kbQa(v, 5, sessionId);
    think.remove();
    if (!res.success) {
      appendAi(`**出错了：** ${res.message || '请确认后端已启动'}`, [], false);
      busy = false;
      return;
    }
    if (!sessionId) sessionId = res.session_id;
    appendAi(res.answer || '（无回答）', res.sources || [], res.sparse);
    body.scrollTop = body.scrollHeight;
    // 会话标题可能是自动摘要后的，刷新列表但不重建消息
    loadSessions(false);
    busy = false;
  }

  ta.addEventListener('input', () => { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 140) + 'px'; });
  ta.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(); } });
  $('#sendBtn').addEventListener('click', ask);
  $('#newChatBtn').addEventListener('click', newChat);
  $('#renameBtn').addEventListener('click', async () => {
    if (!sessionId) { toast('先选择一个会话', 'alert'); return; }
    const title = prompt('重命名会话', $('#chatTitle').textContent);
    if (!title || !title.trim()) return;
    const res = await IA.kbChatRenameSession(sessionId, title.trim());
    if (res.success) { $('#chatTitle').textContent = title.trim(); loadSessions(false); toast('已重命名'); }
    else toast(res.message || '重命名失败', 'alert');
  });

  /* ---------- 语音输入 ---------- */
  const voice = window.createVoiceInput({
    onResult: (text) => {
      $('#micBtn').classList.remove('is-live');
      ta.value = (ta.value ? ta.value + ' ' : '') + text;
      ta.focus();
    },
    onError: (msg) => { $('#micBtn').classList.remove('is-live'); toast(msg, 'alert'); },
  });
  $('#micBtn').addEventListener('click', async () => {
    if (voice.processing()) return;
    if (voice.recording()) { await voice.stop(); return; }
    const ok = await voice.start();
    if (ok) $('#micBtn').classList.add('is-live');
  });

  if (IA.requireAuth()) {
    loadSessions();
    if (!sessions.length) {
      $('#chatBody').innerHTML = `<div class="empty" style="margin:30px 20px"><div class="empty-title">问点什么吧</div>
        <div class="empty-sub">回答仅基于你的知识库，并附带来源</div></div>`;
    }
  }
})();
