/* ============================================================
   我的笔记 · 真实数据
   /kb/notes 列表(搜索/标签/分类) + 分类聚合 + 文件导入 + 网址收藏 + 重建索引
   ============================================================ */
(() => {
  'use strict';
  const IA = window.IA;
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  const state = { q: '', tag: '', category: '' };

  const GLYPH = { note: ['pen', 'note'], file: ['file', 'file'], url: ['link', 'url'] };

  function stripWiki(t) {
    return String(t || '').replace(/\[\[([^\]]+)\]\]/g, '$1').replace(/[#>*`-]/g, '').trim();
  }
  function fmtDate(s) {
    const t = String(s || '');
    return t.length >= 10 ? t.slice(5, 7) + '-' + t.slice(8, 10) : t;
  }

  function renderChips(cats) {
    const catBox = $('#catChips');
    const items = [{ category: '', count: null }].concat(cats || []);
    catBox.innerHTML = items.map((c) => {
      const label = c.category || '全部';
      const n = c.count != null ? ` (${c.count})` : '';
      const on = (state.category || '') === c.category ? ' is-on' : '';
      return `<button class="tag${on}" data-cat="${esc(c.category)}"><span data-ic="folder"></span>${esc(label)}${n}</button>`;
    }).join('');
    if (window.renderIcons) renderIcons(catBox);
    catBox.querySelectorAll('[data-cat]').forEach((b) => b.addEventListener('click', () => {
      state.category = b.dataset.cat;
      load();
    }));
  }

  function renderTagChips(notes) {
    const box = $('#tagChips');
    const freq = new Map();
    (notes || []).forEach((n) => String(n.tags || '').split(',').forEach((t) => {
      const tag = t.trim();
      if (tag) freq.set(tag, (freq.get(tag) || 0) + 1);
    }));
    const top = [...freq.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
    box.innerHTML = top.map(([t]) => `<button class="tag${state.tag === t ? ' is-on' : ''}" data-tag="${esc(t)}">${esc(t)}</button>`).join('');
    box.querySelectorAll('[data-tag]').forEach((b) => b.addEventListener('click', () => {
      state.tag = state.tag === b.dataset.tag ? '' : b.dataset.tag;
      load();
    }));
  }

  function renderNotes(notes) {
    const grid = $('#notesGrid');
    $('#gridStat').textContent = `共 ${notes.length} 篇`;
    if (!notes.length) {
      grid.innerHTML = '<div class="empty" style="grid-column:1/-1"><div class="empty-title">没有匹配的笔记</div>'
        + '<div class="empty-sub">换一个关键词，或<a href="note.html?mode=new" style="color:var(--vermilion)">新建一条笔记 →</a></div></div>';
      return;
    }
    grid.innerHTML = notes.map((n, i) => {
      const type = GLYPH[n.note_type] ? n.note_type : 'note';
      const [ic, cls] = GLYPH[type];
      const tags = String(n.tags || '').split(',').map((t) => t.trim()).filter(Boolean).slice(0, 2);
      const linkIcon = window.iconEl('link');
      const srcIcon = n.source ? `<a class="src" href="${esc(n.source)}" target="_blank" rel="noopener" title="打开原网址">${window.iconEl('external')}</a>` : '';
      const srcOpen = n.source ? ` data-src="${esc(n.source)}"` : '';
      return `<article class="note-card${i % 3 === 0 ? ' tall' : ''} sheet sheet-hover rv is-in" data-id="${esc(n.id)}"${srcOpen}>`
        + `<div class="head"><span class="type-glyph ${cls}">${window.iconEl(ic)}</span>`
        + `<span class="title">${esc(n.title)}</span>${srcIcon}</div>`
        + `<p class="excerpt">${esc(stripWiki(n.content))}</p>`
        + `<div class="meta">${n.category ? `<span class="tag small">${esc(n.category)}</span>` : ''}`
        + tags.map((t) => `<span class="tag small" style="cursor:default">${esc(t)}</span>`).join('')
        + `<span class="links">${linkIcon}${n.link_count || 0}</span>`
        + `<span class="date">${esc(fmtDate(n.updated_at || n.created_at))}</span></div></article>`;
    }).join('');
    grid.querySelectorAll('.note-card').forEach((card) => {
      card.addEventListener('click', (e) => {
        if (e.target.closest('.src')) return;
        IA.go('note?id=' + encodeURIComponent(card.dataset.id));
      });
    });
  }

  async function load() {
    const res = await IA.kbListNotes(state.q, state.tag, state.category);
    if (!res.success) {
      $('#notesGrid').innerHTML = `<div class="empty" style="grid-column:1/-1"><div class="empty-title">笔记加载失败</div>
        <div class="empty-sub">${esc(res.message || '')}</div></div>`;
      return;
    }
    const notes = res.notes || [];
    renderNotes(notes);
    renderTagChips(notes);
    if (!state.category && !state.tag && !state.q) {
      const catRes = await IA.kbCategories();
      if (catRes.success) renderChips(catRes.categories || []);
    }
  }

  /* ---------- 搜索（防抖） ---------- */
  let searchTimer = null;
  $('#searchInput').addEventListener('input', (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { state.q = e.target.value.trim(); load(); }, 320);
  });

  /* ---------- 文件导入 ---------- */
  const fileInput = $('#kbFileInput');
  $('#importBtn').addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', async () => {
    const files = [...fileInput.files];
    if (!files.length) return;
    const box = $('#uploadDemo');
    box.hidden = false;
    box.querySelector('.uploads-row, .t').closest('.uploads-head').querySelector('.t').textContent = `Import Result · 上传中（${files.length} 个文件）…`;
    const res = await IA.kbUploadFiles(files);
    fileInput.value = '';
    if (!res.success) {
      box.querySelector('.uploads-head .t').textContent = 'Import Result · 上传失败';
      toast(res.message || '导入失败', 'alert');
      return;
    }
    const rows = [].concat(
      (res.created || []).map((c) => `<div class="uploads-row"><span class="st ok">成功</span><span class="tt">${esc(c.title || c)}</span><span class="meta">已入库 · 向量已同步</span></div>`),
      (res.skipped || []).map((c) => `<div class="uploads-row"><span class="st skip">跳过</span><span class="tt">${esc(c.title || c)}</span><span class="meta">同名笔记已存在</span></div>`),
      (res.failed || []).map((c) => `<div class="uploads-row"><span class="st skip">失败</span><span class="tt">${esc(c.title || c)}</span><span class="meta">${esc(c.error || '解析失败')}</span></div>`),
    );
    box.innerHTML = `<div class="uploads-head"><span class="t">Import Result · ${res.created.length} 成功 / ${res.skipped.length} 跳过</span>
      <button class="icon-btn" style="width:28px;height:28px" onclick="this.closest('.uploads').hidden=true">${window.iconEl('x')}</button></div>${rows.join('')}`;
    toast(`已导入 ${res.created.length} 篇笔记`);
    load();
  });

  /* ---------- 网址收藏 ---------- */
  $('#urlSave').addEventListener('click', async () => {
    const inputs = document.querySelectorAll('#urlDialog .dlg-field .input-box');
    const url = inputs[0].value.trim();
    const title = inputs[1].value.trim();
    const desc = inputs[2].value.trim();
    const category = inputs[3].value.trim();
    if (!url || !desc) { toast('网址与描述为必填', 'alert'); return; }
    const res = await IA.kbCreateUrlNote(url, title, desc, category);
    if (!res.success) { toast(res.message || '收藏失败', 'alert'); return; }
    document.querySelector('#urlDialog [data-close]').click();
    toast('网址已收藏，正文抽取完成');
    load();
  });

  /* ---------- 重建索引 ---------- */
  $('#rebuildBtn').addEventListener('click', async () => {
    const btn = $('#rebuildBtn');
    btn.disabled = true;
    toast('正在重建向量索引与语义边…', 'refresh');
    const res = await IA.kbRebuild();
    btn.disabled = false;
    if (res.success) toast('重建完成：向量索引与语义边已更新');
    else toast(res.message || '重建失败', 'alert');
    load();
  });

  /* ---------- 启动 ---------- */
  const qParam = IA.query().get('q');
  if (qParam) { state.q = qParam; $('#searchInput').value = qParam; }
  if (IA.requireAuth()) load();
})();
