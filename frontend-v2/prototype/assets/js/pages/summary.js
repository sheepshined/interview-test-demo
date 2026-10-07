/* ============================================================
   面试报告页 · 真实数据渲染
   ?id=<report_id> → GET /reports/{id}(md 全文) + /reports/{id}/radar
   四维雷达 SVG 动态成图；薄弱点一键入库(from-report) + 覆盖情况
   ============================================================ */
(() => {
  'use strict';
  const IA = window.IA;
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  const params = IA.query();
  const reportId = params.get('id') || sessionStorage.getItem('reportId') || '';
  if (!reportId) {
    toast('未找到报告编号，请从面试记录进入', 'alert');
  }

  /* ---------- 封面与 KPI ---------- */
  function renderCover(radar) {
    $('.cover-score .big').textContent = Number(radar.avg_score || 0).toFixed(1);
    const parts = [radar.role_title, radar.difficulty_label].filter(Boolean);
    $('.cover-main .role').textContent = parts.join(' · ') || '模拟面试';
    const kv = document.querySelectorAll('.cover-kv > div .v');
    if (kv[0]) kv[0].textContent = (radar.report_id || reportId).slice(-14);
    if (kv[1]) kv[1].textContent = (radar.timestamp || '').replace(/T.*$/, '') || '—';
    if (kv[2]) kv[2].textContent = radar.total_questions;
    if (kv[3]) kv[3].textContent = sessionStorage.getItem('elapsedTime') || '—';
    const kpi = document.querySelectorAll('.kpi .cell .n');
    if (kpi[0]) kpi[0].textContent = radar.total_questions;
    if (kpi[1]) kpi[1].textContent = radar.total_questions;
    if (kpi[2]) kpi[2].textContent = Number(radar.avg_score || 0).toFixed(1);
    if (kpi[3]) kpi[3].textContent = sessionStorage.getItem('elapsedTime') || '—';
  }

  /* ---------- 雷达 SVG（四维动态成图） ---------- */
  function renderRadar(dims) {
    const poly = $('#radarPoly');
    if (!poly) return;
    const CX = 170, CY = 150, RT = 110, RX = 130;
    const v = (x) => Math.max(0, Math.min(10, Number(x) || 0)) / 10;
    const pts = [
      [CX, CY - RT * v(dims.accuracy)],
      [CX + RX * v(dims.completeness), CY],
      [CX, CY + RT * v(dims.depth)],
      [CX - RX * v(dims.clarity), CY],
    ];
    poly.setAttribute('d', 'M' + pts.map((p) => p.map((n) => n.toFixed(1)).join(' ')).join(' L') + ' Z');
    const dots = $('#radarDots');
    if (dots) {
      dots.querySelectorAll('circle').forEach((c, i) => {
        c.setAttribute('cx', pts[i][0].toFixed(1));
        c.setAttribute('cy', pts[i][1].toFixed(1));
      });
    }
    const vals = document.querySelectorAll('#radarVals text');
    const put = (t, x, y, text) => { if (t) { t.setAttribute('x', x.toFixed(1)); t.setAttribute('y', y.toFixed(1)); t.textContent = text; } };
    put(vals[0], CX, pts[0][1] + 16, (Number(dims.accuracy) || 0).toFixed(1));
    put(vals[1], pts[1][0] + 26, CY + 4, (Number(dims.completeness) || 0).toFixed(1));
    put(vals[2], CX, pts[2][1] - 12, (Number(dims.depth) || 0).toFixed(1));
    put(vals[3], pts[3][0] - 26, CY + 4, (Number(dims.clarity) || 0).toFixed(1));
  }

  /* ---------- 四维进度条 ---------- */
  function renderDims(dims) {
    const meta = [
      ['准确', 'Accuracy', dims.accuracy], ['完整', 'Completeness', dims.completeness],
      ['深度', 'Depth', dims.depth], ['条理', 'Clarity', dims.clarity],
    ];
    $('#dims').innerHTML = meta.map(([cn, en, val]) => {
      const v = Math.max(0, Math.min(10, Number(val) || 0));
      const low = v < 7 ? ' class="low"' : '';
      return '<div class="dim-line"><div class="top"><span class="name">' + cn + '<small>' + en + '</small></span>'
        + '<span class="val"' + low + '>' + v.toFixed(1) + '</span></div>'
        + '<div class="progress"><div class="progress-fill" data-w="' + (v * 10).toFixed(0) + '" style="width:0"></div></div></div>';
    }).join('');
    if (window.initReveal) initReveal();
  }

  /* ---------- 分类 / 强弱项 / 建议 / 好差答案 ---------- */
  function renderCategories(cats) {
    const box = $('#catRows');
    if (!cats || !cats.length) { box.parentElement.style.display = 'none'; return; }
    box.innerHTML = cats.map((c) => {
      const v = Number(c.avg_score || 0);
      return '<div class="cat-row"><span class="c">' + esc(c.category) + '</span>'
        + '<span class="track"><i' + (v >= 8 ? ' class="top"' : '') + ' data-w="' + (v * 10).toFixed(0) + '" style="width:0"></i></span>'
        + '<span class="v">' + v.toFixed(1) + '</span><span class="n">' + (c.count || 0) + ' 题</span></div>';
    }).join('');
    if (window.initReveal) initReveal();
  }

  function renderSw(radar) {
    const fill = (sel, arr, empty) => {
      const box = $(sel);
      box.innerHTML = (arr && arr.length ? arr : [empty]).map((t) => '<li>' + esc(t) + '</li>').join('');
    };
    fill('#swGood', radar.strengths, '本场暂无明显优势项，继续保持作答节奏。');
    fill('#swBad', radar.weaknesses, '本场暂无待加强项。');
  }

  function renderAdvice(items) {
    const box = $('#adviceList');
    $('#importState').textContent = '尚未入库 · 共 ' + items.length + ' 条建议';
    if (!items.length) {
      box.innerHTML = '<div class="empty"><div class="empty-title">本场没有生成学习建议</div><div class="empty-sub">多打几场，建议会更具体</div></div>';
      return;
    }
    box.innerHTML = items.map((s, i) =>
      '<div class="advice-item"><span class="no">' + String(i + 1).padStart(2, '0') + '</span>'
      + '<div><h4>' + esc(s.topic) + '</h4><p>' + esc(s.suggestion) + '</p></div></div>').join('');
  }

  function renderCompare(questions) {
    const box = $('#compareList');
    const qs = (questions || []).filter((q) => (q.good_points || []).length || (q.bad_points || []).length);
    if (!qs.length) { box.innerHTML = '<div class="empty"><div class="empty-title">暂无好差答案对照</div><div class="empty-sub">回答更充分后会出现逐题对照</div></div>'; return; }
    box.innerHTML = qs.map((q) =>
      '<div class="compare rv is-in"><div class="q"><b>Q' + (q.round || '?') + '</b>' + esc(q.question) + '</div>'
      + '<div class="compare-grid">'
      + '<div class="cmp good"><h5><span data-ic="thumbsUp"></span>高分答案特征</h5><ul>'
      + (q.good_points || []).map((t) => '<li>' + esc(t) + '</li>').join('') + '</ul></div>'
      + '<div class="cmp bad"><h5><span data-ic="thumbsDown"></span>低分踩坑特征</h5><ul>'
      + (q.bad_points || []).map((t) => '<li>' + esc(t) + '</li>').join('') + '</ul></div>'
      + '</div></div>').join('');
    if (window.renderIcons) renderIcons(box);
  }

  /* ---------- 报告全文 ---------- */
  function renderDoc(md) {
    const box = $('#reportDoc');
    box.innerHTML = window.renderMd(md);
    box.querySelectorAll('.wikilink').forEach((w) => w.addEventListener('click', () => {
      IA.go('workspace?q=' + encodeURIComponent(w.dataset.wiki));
    }));
  }

  /* ---------- 一键入库 + 覆盖情况 ---------- */
  let radarData = null;
  let imported = false;
  async function importToKb() {
    if (imported || !radarData) return;
    const btn = $('#importBtn');
    const items = (radarData.learning_suggestions || []).map((s) => ({ topic: s.topic, suggestion: s.suggestion }));
    if (!items.length) { toast('没有可入库的建议', 'alert'); return; }
    btn.disabled = true;
    $('#importState').textContent = '正在入库 · 检索关联笔记中…';
    const res = await IA.kbImportFromReport(items, reportId);
    btn.disabled = false;
    if (!res.success) {
      $('#importState').textContent = '入库失败，可重试';
      toast(res.message || '入库失败', 'alert');
      return;
    }
    imported = true;
    const skipped = (res.skipped || []).length;
    $('#importState').textContent = `已入库 ${res.created.length} 条` + (skipped ? ` · ${skipped} 条同名跳过` : '') + ' · 双链已自动建立';
    toast(`已存入知识库 ${res.created.length} 条`);
    renderCoverage(res.coverage || []);
  }

  function renderCoverage(coverage) {
    const box = $('#coverage');
    if (!coverage.length) { box.hidden = true; return; }
    box.innerHTML = '<h5><span data-ic="target"></span>知识库覆盖情况</h5><ul>' + coverage.map((c) => {
      const name = esc(c.topic || '');
      if (c.sparse) {
        return '<li><span class="ic warn" data-ic="alert"></span><span>' + name + '：知识库中暂无相关内容，'
          + '<a href="workspace.html">建议导入对应资料 →</a></span></li>';
      }
      const notes = (c.related_notes || []).map((n) =>
        '<a href="note.html?id=' + encodeURIComponent(n.id) + '">「' + esc(n.title) + '」</a>').join('、');
      return '<li><span class="ic ok" data-ic="checkCircle"></span><span>' + name + '：已有 '
        + (c.related_count || (c.related_notes || []).length) + ' 条相关笔记 ' + notes + '</span></li>';
    }).join('') + '</ul>';
    box.hidden = false;
    if (window.renderIcons) renderIcons(box);
  }

  /* ---------- 启动 ---------- */
  async function load() {
    if (!reportId) {
      $('#reportDoc').innerHTML = '<p>缺少报告编号。<a href="records.html">回到面试记录 →</a></p>';
      return;
    }
    const [rep, radarRes] = await Promise.all([
      IA.getReport(reportId),
      IA.getReportRadar(reportId),
    ]);
    if (!rep.success) {
      toast(rep.message || '报告加载失败', 'alert');
      $('#reportDoc').innerHTML = '<p>' + esc(rep.message || '报告加载失败') + '</p>';
      return;
    }
    // /reports/{id} 返回 {success, report: md}；radar 直接返回 JSON
    const md = typeof rep.report === 'string' ? rep.report : (rep.report && rep.report.content) || (rep.content || '');
    renderDoc(md);
    const radar = radarRes && (radarRes.radar || radarRes);
    if (radar && radar.success !== false && radar.avg_score != null) {
      radarData = radar;
      renderCover(radar);
      renderRadar(radar.dimensions || {});
      renderDims(radar.dimensions || {});
      renderCategories(radar.categories);
      renderSw(radar);
      renderAdvice(radar.learning_suggestions || []);
      renderCompare(radar.questions || []);
    } else {
      toast('雷达数据加载失败', 'alert');
    }
  }

  if (IA.requireAuth()) {
    load();
  }
})();
