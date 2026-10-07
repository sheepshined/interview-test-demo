/* ============================================================
   笔记编辑 · 真实数据
   ?id= 加载(kbGetNote 含 backlinks) / ?mode=new 新建
   保存(create/update) · 整理排版(tidy) · 自动分类(auto-category)
   智能关联(auto-link) · 编辑/预览切换(renderMd + [[双链]])
   ============================================================ */
(() => {
  'use strict';
  const IA = window.IA;
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  const params = IA.query();
  const noteId = params.get('id');
  const isNew = params.get('mode') === 'new' || !noteId;

  const titleInput = $('.title-input');
  const catInput = $('#catInput');
  const tagInput = $('#tagInput');
  const ta = document.querySelector('.paper-area textarea');
  const preview = $('#preview');
  let savedId = isNew ? null : Number(noteId);
  let dirty = false;

  /* ---------- 元信息 ---------- */
  function setMeta(note) {
    $('#metaType').textContent = note.note_type === 'file' ? '文件笔记' : note.note_type === 'url' ? '网址收藏' : '手写笔记';
    $('#metaCreated').textContent = (note.created_at || '').replace('T', ' ').slice(0, 10) || '—';
    $('#metaUpdated').textContent = (note.updated_at || '').replace('T', ' ').slice(0, 16) || '—';
    $('#metaWords').textContent = (note.content || '').length;
    $('#metaRef').textContent = (note.link_count != null ? note.link_count : '—');
  }
  function setIndexBadge(synced) {
    $('#metaIndex').innerHTML = synced
      ? '<span class="badge pine"><span class="dot pine"></span>已同步</span>'
      : '<span class="badge ochre"><span class="dot ochre"></span>未保存</span>';
  }

  /* ---------- 反向链接 / 相关笔记 ---------- */
  function renderBacklinks(backlinks) {
    const box = $('#backlinkList');
    const list = backlinks || [];
    $('#backlinkCount').textContent = '反向链接 · ' + list.length;
    if (!list.length) {
      box.innerHTML = '<p class="empty-sub" style="padding:10px 0">还没有笔记链接到这里；用右上角「智能关联」自动补链。</p>';
      return;
    }
    box.innerHTML = list.map((b) =>
      `<a class="backlink" href="note.html?id=${encodeURIComponent(b.id)}">
        <span class="t"><span data-ic="pen"></span>${esc(b.title)}</span>
        ${b.snippet ? `<span class="ctx">…${esc(b.snippet)}…</span>` : ''}
      </a>`).join('');
    if (window.renderIcons) renderIcons(box);
  }

  async function renderRelated() {
    const box = $('#relatedList');
    const res = await IA.kbGraph(true, '');
    if (!res.success) { box.innerHTML = '<p class="empty-sub" style="padding:10px 0">语义关联加载失败</p>'; return; }
    const title = titleInput.value.trim();
    if (!title) { box.innerHTML = '<p class="empty-sub" style="padding:10px 0">保存标题后可查看语义相关笔记。</p>'; return; }
    const edges = (res.edges || []).filter((e) =>
      (e.kind || e.type) === 'semantic' && (e.source === title || e.target === title));
    if (!edges.length) {
      box.innerHTML = '<p class="empty-sub" style="padding:10px 0">暂无语义关联；重建索引后会重新计算。</p>';
      return;
    }
    const nodes = res.nodes || [];
    box.innerHTML = edges.map((e) => {
      const otherTitle = e.source === title ? e.target : e.source;
      const node = nodes.find((n) => n.id === otherTitle);
      const pct = Math.round((e.score || 0) * 100);
      return `<div class="related"><span class="t">${esc(otherTitle)}</span><span class="sim">${pct}%</span>
        <button class="insert" data-title="${esc(otherTitle)}">插入</button></div>`;
    }).join('');
    box.querySelectorAll('.insert').forEach((b) => b.addEventListener('click', () => {
      ta.value = (ta.value ? ta.value + '\n' : '') + `相关：[[${b.dataset.title}]]`;
      dirty = true;
      toast('已插入 [[' + b.dataset.title + ']]');
    }));
  }

  /* ---------- 加载 ---------- */
  async function loadNote() {
    if (isNew) {
      $('#noteBadge').textContent = '手写笔记';
      $('#noteNo').textContent = '新建 · NEW';
      setIndexBadge(false);
      return;
    }
    const res = await IA.kbGetNote(noteId);
    if (!res.success) {
      toast(res.message || '笔记加载失败', 'alert');
      $('#noteNo').textContent = '加载失败';
      return;
    }
    const note = res.note;
    savedId = note.id;
    titleInput.value = note.title || '';
    catInput.value = note.category || '';
    tagInput.value = note.tags || '';
    ta.value = note.content || '';
    $('#noteBadge').innerHTML = note.note_type === 'file'
      ? '<span data-ic="file"></span>文件笔记'
      : note.note_type === 'url' ? '<span data-ic="link"></span>网址收藏'
      : '<span data-ic="pen"></span>手写笔记';
    $('#noteNo').textContent = 'NOTE № ' + String(note.id).padStart(2, '0') + ' · 创建于 ' + (note.created_at || '').slice(5, 10).replace('-', '-');
    setMeta(note);
    setIndexBadge(true);
    renderBacklinks(res.backlinks);
    if (window.renderIcons) renderIcons($('#noteBadge'));
    if (window.initReveal) initReveal();
  }

  /* ---------- 保存 ---------- */
  async function save() {
    const title = titleInput.value.trim();
    if (!title) { toast('先给笔记起个标题', 'alert'); return; }
    const tags = tagInput.value.split(',').map((t) => t.trim()).filter(Boolean);
    const category = catInput.value.trim();
    if (savedId == null) {
      const res = await IA.kbCreateNote(title, ta.value, tags, category);
      if (!res.success) { toast(res.message || '创建失败', 'alert'); return; }
      savedId = res.note_id || res.id || (res.note && res.note.id);
      toast('笔记已创建 · 向量已同步');
    } else {
      const res = await IA.kbUpdateNote(savedId, title, ta.value, tags, category);
      if (!res.success) { toast(res.message || '保存失败', 'alert'); return; }
      toast('已保存 · 已同步向量索引');
    }
    dirty = false;
    setIndexBadge(true);
    if (window.__SPA) window.location.hash = '#/note?id=' + savedId; else history.replaceState(null, '', 'note.html?id=' + savedId);
    const res2 = await IA.kbGetNote(savedId);
    if (res2.success) { setMeta(res2.note); renderBacklinks(res2.backlinks); }
    renderRelated();
  }
  $('#saveBtn').addEventListener('click', save);
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); save(); }
  });

  /* ---------- AI 工具 ---------- */
  $('#tidyBtn').addEventListener('click', async () => {
    if (savedId == null) { toast('先保存笔记再整理', 'alert'); return; }
    const btn = $('#tidyBtn');
    btn.disabled = true;
    toast('AI 整理排版中…', 'sparkle');
    const res = await IA.kbTidy(savedId);
    btn.disabled = false;
    if (!res.success) { toast(res.message || '整理失败', 'alert'); return; }
    const content = res.content || (res.note && res.note.content);
    if (content) ta.value = content;
    toast('整理排版完成：已统一标题层级与列表格式');
  });

  $('#autocatBtn').addEventListener('click', async () => {
    if (savedId == null) { toast('先保存笔记再自动分类', 'alert'); return; }
    const btn = $('#autocatBtn');
    btn.disabled = true;
    const res = await IA.kbAutoCategory(savedId);
    btn.disabled = false;
    if (!res.success) { toast(res.message || '分类失败', 'alert'); return; }
    catInput.value = res.category || catInput.value;
    toast('已自动归类到「' + (res.category || '未分类') + '」');
  });

  $('#autolinkBtn').addEventListener('click', async () => {
    if (savedId == null) { toast('先保存笔记再智能关联', 'alert'); return; }
    const btn = $('#autolinkBtn');
    btn.disabled = true;
    toast('正在检索相关笔记并追加双链…', 'link');
    const res = await IA.kbAutoLink(savedId);
    btn.disabled = false;
    if (!res.success) { toast(res.message || '关联失败', 'alert'); return; }
    const added = res.linked != null ? res.linked : (res.added || (res.links || []).length);
    toast(added > 0 ? `已追加 ${added} 条 [[双链]] 到相关笔记` : (res.message || '没有需要补链的新关联'));
    const res2 = await IA.kbGetNote(savedId);
    if (res2.success) { ta.value = res2.note.content || ta.value; renderBacklinks(res2.backlinks); }
    renderRelated();
  });

  /* ---------- 删除 ---------- */
  $('#deleteBtn').addEventListener('click', async () => {
    if (savedId == null) { IA.go('workspace'); return; }
    if (!confirm('删除这篇笔记？向量与图谱会同步更新。')) return;
    const res = await IA.kbDeleteNote(savedId);
    if (res.success) { toast('已删除'); setTimeout(() => { IA.go('workspace'); }, 500); }
    else toast(res.message || '删除失败', 'alert');
  });

  /* ---------- 编辑 / 预览 ---------- */
  const tabEdit = $('#tabEdit'), tabPreview = $('#tabPreview');
  function setMode(edit) {
    tabEdit.classList.toggle('is-on', edit);
    tabPreview.classList.toggle('is-on', !edit);
    ta.classList.toggle('is-off', !edit);
    preview.classList.toggle('is-on', !edit);
    if (!edit) {
      preview.innerHTML = window.renderMd(ta.value);
      preview.querySelectorAll('.wikilink').forEach((w) => w.addEventListener('click', () => {
        IA.go('workspace?q=' + encodeURIComponent(w.dataset.wiki));
      }));
    }
  }
  tabEdit.addEventListener('click', () => setMode(true));
  tabPreview.addEventListener('click', () => setMode(false));

  /* ---------- 稿纸高度 + 脏标记 ---------- */
  ta.addEventListener('input', () => {
    ta.style.height = 'auto';
    ta.style.height = ta.scrollHeight + 'px';
    dirty = true;
    setIndexBadge(false);
  });

  /* ---------- 启动 ---------- */
  if (IA.requireAuth()) {
    setIndexBadge(false);
    loadNote();
    renderRelated();
  }
})();
