/* ============================================================
   知识图谱 · 真实数据（cytoscape + fcose，与 GraphView 同源参数）
   GET /kb/graph?semantic=&category= → nodes/edges
   悬停聚焦邻域 · 点击进笔记/创建虚笔记 · 语义边开关 · 分类筛选
   ============================================================ */
(() => {
  'use strict';
  const IA = window.IA;
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  const TYPE_STYLE = {
    note: { color: '#23405C', border: '#23405C' },
    file: { color: '#2E6B50', border: '#2E6B50' },
    url: { color: '#A9741C', border: '#A9741C' },
    virtual: { color: 'rgba(23,21,15,0.06)', border: 'rgba(23,21,15,0.4)' },
  };
  const typeOf = (n) => n.virtual ? 'virtual' : (n.note_type || 'note');
  const typeLabel = (n) => n.virtual
    ? '未创建 · 虚拟节点'
    : ({ file: '文件笔记', url: '网址收藏' }[n.note_type] || '手写笔记') + (n.category ? ' · ' + n.category : '');

  let cy = null;
  let hideIsolated = false;

  function buildCy(data) {
    const nodes = data.nodes || [];
    const edges = data.edges || [];
    if (cy) cy.destroy();
    cy = cytoscape({
      container: $('#cy'),
      elements: [
        ...nodes.map((n) => ({
          data: {
            id: n.id, title: n.id, note_id: n.note_id, degree: n.degree || 0,
            category: n.category || '', tags: n.tags || [], note_type: n.note_type || 'note',
            virtual: !!n.virtual, source_url: n.source_url || '',
            tcolor: TYPE_STYLE[typeOf(n)].color,
          },
        })),
        ...edges.map((e, i) => ({
          data: {
            id: 'e' + i, source: e.source, target: e.target,
            kind: e.kind || e.type || 'wiki', score: e.score || 0,
          },
        })),
      ],
      style: [
        { selector: 'node', style: {
          'width': 'mapData(degree, 0, 8, 14, 40)',
          'height': 'mapData(degree, 0, 8, 14, 40)',
          'background-color': 'data(tcolor)',
          'border-width': (ele) => (ele.data('virtual') ? 1.4 : 2),
          'border-style': (ele) => (ele.data('virtual') ? 'dashed' : 'solid'),
          'border-color': TYPE_STYLE.virtual.border,
          'label': 'data(title)',
          'font-family': 'JetBrains Mono, monospace',
          'font-size': 9,
          'color': '#4C4739',
          'text-valign': 'bottom',
          'text-margin-y': 7,
          'text-background-color': '#F4F1E8',
          'text-background-opacity': 0.85,
          'text-background-padding': 2,
          'text-max-width': 96,
          'text-wrap': 'ellipsis',
          'opacity': (ele) => (hideIsolated && ele.degree() === 0 ? 0.12 : 1),
        } },
        { selector: 'edge', style: {
          'width': 1,
          'line-color': 'rgba(23,21,15,0.28)',
          'curve-style': 'haystack',
          'haystack-radius': 0.4,
          'opacity': 0.55,
        } },
        { selector: 'edge[kind="semantic"]', style: {
          'line-style': 'dashed',
          'line-color': 'rgba(217,58,31,0.36)',
          'line-dash-pattern': [3, 5],
          'opacity': 0.4,
        } },
        { selector: 'node.faded, edge.faded', style: { opacity: 0.08 } },
        { selector: 'node.active', style: { 'border-color': '#D93A1F', 'border-width': 2.4 } },
      ],
      layout: { name: 'grid' },
      wheelSensitivity: 0.25,
    });
    // 统计条先更新（布局失败也不影响信息展示）
    const wikiCount = edges.filter((e) => (e.kind || e.type) === 'wiki').length;
    const semCount = edges.filter((e) => (e.kind || e.type) === 'semantic').length;
    $('#graphStat').innerHTML = `<b>${nodes.filter((n) => !n.virtual).length}</b> 节点 · <b>${nodes.filter((n) => n.virtual).length}</b> 虚拟 · <b>${wikiCount}</b> 双链 · <b>${semCount}</b> 语义`;
    runLayout();
    bindCy();
  }

  function runLayout() {
    if (!cy) return;
    try {
      cy.layout({
        name: 'cose',
        animate: false,
        randomize: true,
        nodeOverlap: 24,
        idealEdgeLength: (e) => (e.data('kind') === 'semantic' ? 140 : 70),
        nodeRepulsion: 9000,
        gravity: 0.5,
        componentSpacing: 90,
        padding: 30,
      }).run();
    } catch (e) {
      try { cy.layout({ name: 'grid' }).run(); } catch (_) {}
    }
  }

  function bindCy() {
    cy.on('mouseover', 'node', (e) => {
      const n = e.target;
      cy.elements().addClass('faded');
      n.removeClass('faded').addClass('active');
      n.neighborhood().removeClass('faded');
      $('#ncTitle').textContent = n.data('title');
      $('#ncType').textContent = typeLabel({
        virtual: n.data('virtual'), note_type: n.data('note_type'), category: n.data('category'),
      });
      $('#ncLinks').textContent = n.data('degree');
      $('#ncNote').textContent = (n.data('tags') || []).join(' / ') || (n.data('virtual') ? '点击可创建该笔记' : '双链节点');
      $('#ncHint').textContent = n.data('virtual')
        ? '点击 → 以该标题创建笔记'
        : (n.data('source_url') ? '点击打开原网址 · 或进笔记编辑' : '点击进入笔记编辑');
      $('#nodeCard').classList.add('is-on');
    });
    cy.on('mouseout', 'node', () => {
      cy.elements().removeClass('faded');
      cy.nodes().removeClass('active');
      $('#nodeCard').classList.remove('is-on');
    });
    cy.on('tap', 'node', async (e) => {
      const n = e.target;
      if (n.data('virtual')) {
        if (!confirm(`以「${n.data('title')}」为标题创建新笔记？`)) return;
        const res = await IA.kbCreateNote(n.data('title'), '');
        if (res.success) {
          toast('笔记已创建，图谱中已是实体节点');
          loadGraph();
        } else toast(res.message || '创建失败', 'alert');
        return;
      }
      IA.go('note?id=' + encodeURIComponent(n.data('note_id')));
    });
  }

  /* ---------- 数据加载 ---------- */
  let semantic = true;
  let category = '';
  async function loadGraph() {
    const res = await IA.kbGraph(semantic, category);
    if (!res.success) {
      $('#cy').innerHTML = `<div class="empty" style="margin:40px"><div class="empty-title">图谱加载失败</div>
        <div class="empty-sub">${esc(res.message || '')}</div></div>`;
      return;
    }
    buildCy(res.graph || res);
  }

  /* ---------- 工具条 ---------- */
  $('#semToggle').addEventListener('change', (e) => { semantic = e.target.checked; loadGraph(); });
  $('#isolatedToggle').addEventListener('change', (e) => {
    hideIsolated = e.target.checked;
    cy.nodes().forEach((n) => {
      if (hideIsolated && n.degree() === 0) n.style('opacity', 0.12);
      else n.removeStyle('opacity');
    });
  });
  $('#rebuildBtn').addEventListener('click', async () => {
    $('#rebuildBtn').disabled = true;
    toast('正在重建向量索引与语义边…', 'refresh');
    const res = await IA.kbRebuild();
    $('#rebuildBtn').disabled = false;
    if (res.success) { toast('重建完成'); loadGraph(); }
    else toast(res.message || '重建失败', 'alert');
  });
  $('#relayoutBtn').addEventListener('click', runLayout);

  async function loadCategories() {
    const res = await IA.kbCategories();
    if (!res.success) return;
    const cats = res.categories || [];
    const box = $('#catChips');
    box.innerHTML = [{ category: '', count: null }].concat(cats).map((c) =>
      `<button class="tag${category === c.category ? ' is-on' : ''}" data-cat="${esc(c.category)}">`
      + `<span data-ic="folder"></span>${esc(c.category || '全部分类')}${c.count != null ? ' (' + c.count + ')' : ''}</button>`).join('');
    if (window.renderIcons) renderIcons(box);
    box.querySelectorAll('[data-cat]').forEach((b) => b.addEventListener('click', () => {
      category = b.dataset.cat;
      loadGraph();
      loadCategories();
    }));
  }

  if (IA.requireAuth()) {
    loadCategories();
    loadGraph();
  }
})();
