/* ============================================================
   墨卷档案 · SPA 路由（外壳 app.html）
   hash 路由 #/page?query → fetch 对应静态页 → 抽取 .main 内容与
   页面样式/脚本 → 注入换页（旧页滑出 / 新页滑入）→ 重执行页面脚本。
   共享脚本不重复执行；页面用 IA.pageCleanup 注册换页清理。
   ============================================================ */
(() => {
  'use strict';
  const IA = window.IA;
  if (!IA.isAuthenticated()) { location.href = 'login.html'; return; }

  window.__SPA = true;

  /* 可免刷新换页的路由（对应同名 .html） */
  const ROUTES = new Set(['resume', 'matching', 'choose-job', 'records', 'summary', 'workspace', 'note', 'graph', 'chat']);
  window.__SPA_ROUTES = ROUTES;
  const RAIL_MAP = {
    resume: 'resume', matching: 'resume', 'choose-job': 'choose',
    records: 'records', summary: 'records',
    workspace: 'workspace', note: 'workspace',
    graph: 'graph', chat: 'chat',
  };
  /* 共享脚本不重复执行 */
  const SHARED = new Set(['app.js', 'api.js', 'md.js', 'voice.js', 'interactions.js', 'router.js', 'cytoscape.min.js']);

  const mainEl = document.getElementById('appMain');
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const cache = new Map();
  let navSeq = 0;
  const SHELL_EPOCH = Date.now(); // 防跨会话脚本缓存碰撞

  function parseHash() {
    const h = location.hash.replace(/^#\/?/, '');
    if (!h) return { page: 'choose-job' };
    const q = h.indexOf('?');
    return { page: q === -1 ? h : h.slice(0, q) };
  }

  function setActiveRail(page) {
    const railPage = RAIL_MAP[page];
    document.querySelectorAll('.rail-link').forEach((a) => {
      a.classList.toggle('is-active', a.dataset.railPage === railPage);
    });
  }

  const CACHE_TTL = 30000; // 30s：开发期修改及时生效，正常浏览仍走内存
  function fetchPage(page) {
    const hit = cache.get(page);
    if (hit && Date.now() - hit.at < CACHE_TTL) return hit.p;
    const p = fetch(page + '.html', { cache: 'no-cache' }).then((r) => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.text();
    });
    cache.set(page, { p, at: Date.now() });
    p.catch(() => cache.delete(page));
    return p;
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const el = document.createElement('script');
      el.src = src;
      el.onload = resolve;
      el.onerror = () => reject(new Error('脚本加载失败: ' + src));
      document.body.appendChild(el);
    });
  }

  function runInline(text) {
    (0, eval)(text);
  }


  function errorBox(message) {
    return `<div class="page-body"><div class="empty">
      <div class="empty-title">页面加载失败</div>
      <div class="empty-sub">${message || ''} · <a href="#" onclick="location.reload()" style="color:var(--vermilion)">重试</a></div>
    </div></div>`;
  }


  async function render(page, opts = {}) {
    if (!ROUTES.has(page)) { window.location.href = page + '.html'; return; }
    const seq = ++navSeq;
    IA.runCleanups();
    try { window.speechSynthesis && window.speechSynthesis.cancel(); } catch (_) {}

    let html;
    try { html = await fetchPage(page); }
    catch (e) { mainEl.classList.remove('is-leaving'); mainEl.innerHTML = errorBox(e.message); return; }
    if (seq !== navSeq) return;

    const doc = new DOMParser().parseFromString(html, 'text/html');

    // 页面级样式（延后到「完全淡出后」再切换，避免旧页面闪失样式）
    const styles = [...doc.querySelectorAll('style')].map((s) => s.textContent).join('\n');
    let styleEl = document.getElementById('pageStyle');
    if (!styleEl) {
      styleEl = document.createElement('style');
      styleEl.id = 'pageStyle';
      document.head.appendChild(styleEl);
    }

    // 主区内容 + body 级弹层
    const main = doc.querySelector('.main');
    const overlays = [...doc.querySelectorAll('.mask, .drawer')].map((n) => n.outerHTML).join('');
    const content = (main ? main.innerHTML : '') + overlays;
    if (!content.trim()) { window.location.href = page + '.html'; return; }

    /* ── 快速淡出 → 换装（样式+内容同时）→ 淡入 ──
       淡出等待必须 ≥ 过渡时长（0.16s），保证换装那一刻完全不可见；
       样式与内容在同一时刻切换，旧页面在淡出全程保持自己的样式。 */
    if (!opts.first) {
      mainEl.classList.add('is-leaving');
      await wait(190);
      if (seq !== navSeq) return;
    }
    styleEl.textContent = styles;
    mainEl.innerHTML = content;
    window.scrollTo(0, 0);

    document.title = (doc.title || '面试 · 训练场').replace(' · AI 模拟面试官', '') + ' · AI 模拟面试官';
    document.body.dataset.page = doc.body.dataset.page || page;
    setActiveRail(page);

    // 重执行页面脚本（跳过共享脚本；页面脚本绑定的是刚注入的新 DOM）
    for (const old of [...doc.querySelectorAll('script')]) {
      const src = old.getAttribute('src');
      try {
        if (src) {
          const base = src.split('/').pop().split('?')[0];
          if (SHARED.has(base)) continue;
          await loadScript(src + (src.includes('?') ? '&' : '?') + 'v=' + SHELL_EPOCH + '-' + navSeq);
        } else if (old.textContent.trim()) {
          runInline(old.textContent);
        }
      } catch (e) { console.error('[router] script error:', src || 'inline', e); }
    }

    if (seq !== navSeq) return;
    mainEl.classList.remove('is-leaving');
    renderIcons(mainEl);

    // 页头大标题：淡入时字体浮现（保留）
    const title = mainEl.querySelector('.page-title, .cover-main h1');
    if (title && !title.querySelector('.sw-line')) {
      const inner = title.innerHTML;
      title.innerHTML = '<span class="sw-line"><span>' + inner + '</span></span>';
    }
    if (window.initReveal) initReveal();
    if (window.IX) window.IX.refresh(mainEl);
  }

  /* ---------- 内容区 .html 链接兜底接管 ----------
     立即 preventDefault 挡住浏览器整页跳转；随后延迟比对 hash——
     若页面自己的点击处理器已导航（hash 变化），则以页面为准跳过。 */
  document.addEventListener('click', (e) => {
    if (e.defaultPrevented) return;
    const a = e.target.closest('a[href]');
    if (!a || !mainEl.contains(a)) return;
    const href = a.getAttribute('href') || '';
    if (!href.endsWith('.html') || href.startsWith('http') || a.target === '_blank') return;
    const file = href.split('/').pop().replace('.html', '');
    if (!ROUTES.has(file)) return; // 非路由页（interview/index/login）交给墨幕整页转场

    e.preventDefault();
    const hashAtClick = location.hash;
    setTimeout(() => {
      if (location.hash !== hashAtClick) return; // 页面处理器已自行导航
      const q = href.includes('?') ? href.slice(href.indexOf('?') + 1) : '';
      window.location.hash = '#/' + file + (q ? '?' + q : '');
    }, 0);
  }, true);

  /* ---------- 侧栏悬停预取：点击时零等待 ---------- */
  document.querySelector('.rail').addEventListener('mouseover', (e) => {
    const a = e.target.closest('a[href^="#/"]');
    if (!a) return;
    const page = a.getAttribute('href').replace('#/', '').split('?')[0];
    if (ROUTES.has(page)) fetchPage(page).catch(() => {});
  });

  /* ---------- 路由事件 ---------- */
  window.addEventListener('hashchange', () => {
    const { page } = parseHash();
    if (!ROUTES.has(page)) { window.location.href = page + '.html'; return; }
    render(page);
  });

  /* ---------- 启动 ---------- */
  const first = parseHash();
  render(first.page, { first: true });
})();
