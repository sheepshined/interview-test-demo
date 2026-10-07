/* ============================================================
   墨卷档案 · API 层（frontend/src/api 的零依赖移植）
   自动 Bearer / 超时 / 401 回登录页 / kbFileUrl / 登录态守卫
   依赖 app.js 先加载（toast），须在 app.js 之后引入。
   ============================================================ */
(() => {
  'use strict';

  const TOKEN_KEY = 'interview_auth_token';
  const USERNAME_KEY = 'interview_auth_username';
  const BASE = '/api';

  const DEFAULT_TIMEOUT = 30000;
  const UPLOAD_TIMEOUT = 90000;

  /* ---------- 登录态 ---------- */
  function saveAuth(token, username) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USERNAME_KEY, username);
  }
  function clearAuth() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USERNAME_KEY);
  }
  function getToken() { return localStorage.getItem(TOKEN_KEY) || ''; }
  function getUsername() { return localStorage.getItem(USERNAME_KEY) || ''; }

  function _decodeJwtPayload(token) {
    try {
      const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      const json = decodeURIComponent(atob(base64).split('').map((c) =>
        '%' + c.charCodeAt(0).toString(16).padStart(2, '0')).join(''));
      return JSON.parse(json);
    } catch (_) { return null; }
  }
  function isAuthenticated() {
    const token = getToken();
    const username = getUsername();
    if (!token || !username) return false;
    const payload = _decodeJwtPayload(token);
    if (!payload || payload.username !== username) return false;
    return typeof payload.exp === 'number' && payload.exp * 1000 > Date.now();
  }

  /* 路由守卫：应用壳页面未登录一律回登录页 */
  function requireAuth() {
    if (document.body.dataset.shell === 'app' && !isAuthenticated()) {
      const back = encodeURIComponent(location.pathname.split('/').pop() + location.search);
      location.href = 'login.html?redirect=' + back;
      return false;
    }
    return true;
  }

  /* ---------- 请求核心 ---------- */
  async function request(url, options = {}) {
    const headers = { ...options.headers };
    const isFormData = options.body instanceof FormData;

    if (!options.skipAuth) {
      const token = getToken();
      if (token) headers['Authorization'] = `Bearer ${token}`;
    }
    if (options.body && !isFormData) {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }

    const timeout = options.timeout || DEFAULT_TIMEOUT;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    if (options.signal) options.signal.addEventListener('abort', () => controller.abort());

    let res;
    try {
      res = await fetch(`${BASE}${url}`, { ...options, headers, signal: controller.signal });
    } catch (err) {
      clearTimeout(timer);
      if (err.name === 'AbortError') {
        return { success: false, status: 0, message: '请求超时，请稍后重试（简历解析较慢，最多需 90 秒）' };
      }
      return { success: false, status: 0, message: '无法连接后端服务，请确认 FastAPI 已在 127.0.0.1:8000 启动' };
    } finally {
      clearTimeout(timer);
    }

    if (!res.ok) {
      let detail = '';
      try {
        const errBody = await res.json();
        detail = errBody.detail || errBody.message || '';
      } catch (_) {
        detail = await res.text().catch(() => '');
      }
      if (res.status === 401 && !options.skipAuth) {
        clearAuth();
        location.href = 'login.html';
        return { success: false, status: 401, message: '登录已过期，请重新登录' };
      }
      return {
        success: false,
        status: res.status,
        message: res.status === 404
          ? '接口不存在（404），请确认启动的是当前项目后端'
          : res.status === 500 && !detail
            ? '后端未启动或代理连接失败，请确认 FastAPI 已在 127.0.0.1:8000 启动'
            : `请求失败 (${res.status})` + (detail ? `: ${detail}` : ''),
      };
    }

    try {
      return await res.json();
    } catch (err) {
      return { success: false, message: `响应解析失败: ${err.message}` };
    }
  }

  /* ---------- 全部接口 ---------- */
  const api = {
    request,
    saveAuth, clearAuth, getToken, getUsername, isAuthenticated, requireAuth,

    getRoles: () => request('/roles'),
    login: (username, password) =>
      request('/login', { method: 'POST', body: { username, password }, skipAuth: true }),
    register: (username, password) =>
      request('/register', { method: 'POST', body: { username, password }, skipAuth: true }),

    uploadResume: (file) => {
      const fd = new FormData();
      fd.append('file', file);
      return request('/upload/resume', { method: 'POST', body: fd, timeout: UPLOAD_TIMEOUT });
    },
    parseTextResume: (content) =>
      request('/resume/parse-text', { method: 'POST', body: { content } }),

    kbListNotes: (search = '', tag = '', category = '') =>
      request(`/kb/notes?search=${encodeURIComponent(search)}&tag=${encodeURIComponent(tag)}&category=${encodeURIComponent(category)}`),
    kbGetNote: (id) => request(`/kb/notes/${id}`),
    kbCreateNote: (title, content = '', tags = [], category = '') =>
      request('/kb/notes', { method: 'POST', body: { title, content, tags, category } }),
    kbUpdateNote: (id, title, content, tags, category = '') =>
      request(`/kb/notes/${id}`, { method: 'PUT', body: { title, content, tags, category } }),
    kbDeleteNote: (id) => request(`/kb/notes/${id}`, { method: 'DELETE' }),
    kbGraph: (semantic = true, category = '') =>
      request(`/kb/graph?semantic=${semantic}&category=${encodeURIComponent(category)}`),
    kbCategories: () => request('/kb/categories'),
    kbUploadFiles: (fileList) => {
      const fd = new FormData();
      for (const f of fileList) fd.append('files', f);
      return request('/kb/notes/upload', { method: 'POST', body: fd, timeout: 300000 });
    },
    kbCreateUrlNote: (url, title, description, category = '') =>
      request('/kb/notes/url', { method: 'POST', body: { url, title, description, category } }),
    kbSearch: (q, topK = 5) =>
      request(`/kb/search?q=${encodeURIComponent(q)}&top_k=${topK}`),
    kbQa: (question, topK = 5, sessionId = null) =>
      request('/kb/qa', { method: 'POST', body: { question, top_k: topK, session_id: sessionId }, timeout: 120000 }),
    kbChatListSessions: () => request('/kb/chat/sessions'),
    kbChatCreateSession: () => request('/kb/chat/sessions', { method: 'POST' }),
    kbChatGetSession: (id) => request(`/kb/chat/sessions/${id}`),
    kbChatRenameSession: (id, title) =>
      request(`/kb/chat/sessions/${id}`, { method: 'PATCH', body: { title } }),
    kbChatDeleteSession: (id) =>
      request(`/kb/chat/sessions/${id}`, { method: 'DELETE' }),
    kbTidy: (noteId) => request(`/kb/tidy?note_id=${noteId}`, { method: 'POST', timeout: 180000 }),
    kbAutoCategory: (noteId) => request(`/kb/auto-category?note_id=${noteId}`, { method: 'POST', timeout: 120000 }),
    kbAutoLink: (noteId) => request(`/kb/notes/${noteId}/auto-link`, { method: 'POST', timeout: 120000 }),
    kbRebuild: () => request('/kb/rebuild', { method: 'POST', timeout: 300000 }),
    kbImportFromReport: (items, reportId) =>
      request('/kb/notes/from-report', { method: 'POST', body: { items, report_id: reportId } }),

    getReports: () => request('/reports'),
    getReport: (reportId) => request(`/reports/${reportId}`),
    getReportRadar: (reportId) => request(`/reports/${reportId}/radar`),

    listInterviewRecords: () => request('/interview-records'),
    getInterviewRecord: (filename) => request(`/interview-records/${encodeURIComponent(filename)}`),
    deleteInterviewRecord: (filename) =>
      request(`/interview-records/${encodeURIComponent(filename)}`, { method: 'DELETE' }),

    transcribeAudio: (blob) => {
      const fd = new FormData();
      fd.append('file', blob, 'voice.wav');
      return request('/asr', { method: 'POST', body: fd, timeout: 30000 });
    },

    kbFileUrl: (p) => {
      if (!p) return '#';
      const name = encodeURIComponent(String(p).split('/').pop() || '');
      const token = encodeURIComponent(getToken() || '');
      return `/api/kb/files/${name}?token=${token}`;
    },
  };

  /* 面试配置存取（与原版同 key，行为一致） */
  api.readConfig = () => {
    try {
      return JSON.parse(sessionStorage.getItem('selectedRole')
        || localStorage.getItem('interviewConfig') || 'null');
    } catch (_) { return null; }
  };
  api.writeConfig = (config) => {
    sessionStorage.setItem('selectedRole', JSON.stringify(config));
    localStorage.setItem('interviewConfig', JSON.stringify(config));
  };
  api.readResumeData = () => {
    try { return JSON.parse(sessionStorage.getItem('resumeData') || 'null'); }
    catch (_) { return null; }
  };

  /* ---------- SPA 路由辅助 ---------- */
  // 页面级清理注册表：换页前执行（停计时器 / 关 WS / 解绑 document 监听）
  const cleanups = [];
  api.pageCleanup = (fn) => cleanups.push(fn);
  api.runCleanups = () => { while (cleanups.length) { try { cleanups.pop()(); } catch (_) {} } };

  // 页面参数：外壳内读 hash query，独立页读 location.search
  api.query = () => {
    if (window.__SPA) {
      const h = location.hash.replace(/^#\//, '');
      return new URLSearchParams(h.includes('?') ? h.slice(h.indexOf('?') + 1) : '');
    }
    return new URLSearchParams(location.search);
  };

  // 站内跳转：app 路由走外壳 hash；全屏页/营销页走整页导航（墨幕转场）
  api.go = (dest) => {
    const qIdx = dest.indexOf('?');
    const file = qIdx === -1 ? dest : dest.slice(0, qIdx);
    const q = qIdx === -1 ? '' : dest.slice(qIdx + 1);
    if (file.endsWith('.html')) { window.location.href = dest; return; }
    const target = '#/' + file + (q ? '?' + q : '');
    if (window.__SPA) window.location.hash = target;
    else window.location.href = 'app.html' + target;
  };

  window.IA = api; // Interview API
})();
