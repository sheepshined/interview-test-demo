/* ============================================================
   面试记录页 · 真实数据
   GET /interview-records（列表）+ /{filename}（内容）+ DELETE
   GET /reports（报告档案条，直达 summary.html?id=）
   ============================================================ */
(() => {
  'use strict';
  const IA = window.IA;
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  let records = [];
  let reports = [];
  let current = '';

  /* ---------- 报告档案条 ---------- */
  function renderReports() {
    const box = $('#reportStrip');
    if (!reports.length) {
      box.innerHTML = '<span class="mono">暂无评估报告 · 完成一场面试后自动生成</span>';
      return;
    }
    box.innerHTML = reports.map((r) =>
      '<a class="tag' + (r.avg_score >= 8 ? ' verm' : '') + '" href="summary.html?id=' + encodeURIComponent(r.report_id) + '">'
      + esc(r.role_title || r.report_id) + ' · ' + Number(r.avg_score || 0).toFixed(1) + ' 分 · '
      + esc((r.timestamp || '').slice(4, 6) + '-' + (r.timestamp || '').slice(6, 8)) + '</a>').join('');
  }

  /* ---------- 记录清单 ---------- */
  function renderList() {
    const box = $('#recList');
    $('#recCount').textContent = 'Records · ' + records.length + ' 份';
    if (!records.length) {
      box.innerHTML = '<div class="empty" style="margin:12px"><div class="empty-title">还没有面试记录</div>'
        + '<div class="empty-sub"><a href="choose-job.html">去开启第一场面试 →</a></div></div>';
      return;
    }
    box.innerHTML = records.map((r, i) => {
      const ts = String(r.timestamp || '');
      const time = ts.length >= 13 ? ts.slice(4, 6) + '-' + ts.slice(6, 8) + ' ' + ts.slice(9, 11) + ':' + ts.slice(11, 13) : (r.timestamp || '');
      return '<button class="rec-item' + (i === 0 ? ' is-on' : '') + '" data-fn="' + esc(r.filename) + '">'
        + '<span class="idx">' + String(i + 1).padStart(2, '0') + '</span>'
        + '<span class="body"><span class="role">' + esc(r.role_title || '面试记录') + '</span>'
        + '<span class="meta"><span>' + esc(r.difficulty_label || '—') + '</span><span>·</span>'
        + '<span>' + esc(r.total_count || '?') + ' 题</span><span>·</span><span>' + esc(time) + '</span></span></span>'
        + '<span class="del" title="删除" data-del="' + esc(r.filename) + '"><span data-ic="trash"></span></span>'
        + '</button>';
    }).join('');
    if (window.renderIcons) renderIcons(box);
  }

  /* ---------- 记录内容 ---------- */
  async function openRecord(filename) {
    if (!filename) return;
    current = filename;
    document.querySelectorAll('#recList .rec-item').forEach((el) => {
      el.classList.toggle('is-on', el.dataset.fn === filename);
    });
    const res = await IA.getInterviewRecord(filename);
    if (!res.success) {
      $('#recContent').innerHTML = '<p>' + esc(res.message || '加载失败') + '</p>';
      return;
    }
    const content = res.content || '';
    // 头部元信息行 → 档案头
    const metaLine = content.split('\n').filter((l) => l.includes('**')).slice(0, 6).join(' · ')
      .replace(/\*\*/g, '');
    $('#recFname').textContent = filename;
    const c = metaLine.match(/题量:\s*(\d+)/);
    $('#recSub').textContent = 'Record' + (c ? ' · ' + c[1].trim() + ' questions' : '');

    // 元信息行与正文一起渲染（幂等：容器被整体替换，不依赖悬空元素引用）
    const box = $('#recContent');
    box.innerHTML = '<div class="md-sub">' + esc(metaLine.slice(0, 160)) + '</div>' + window.renderMd(content);
    box.querySelectorAll('h2, h3').forEach((el) => el.classList.add('md-h'));
    box.querySelectorAll('p').forEach((el) => el.classList.add('md-p'));
    box.querySelectorAll('li').forEach((el) => el.classList.add('md-li'));
  }

  /* ---------- 删除 ---------- */
  async function removeRecord(filename, btn) {
    if (!confirm('删除这份面试记录？此操作不可恢复。')) return;
    const res = await IA.deleteInterviewRecord(filename);
    if (res.success) {
      toast('已删除');
      records = records.filter((r) => r.filename !== filename);
      renderList();
      if (current === filename && records.length) openRecord(records[0].filename);
      else if (!records.length) $('#recContent').innerHTML = '<p>记录已清空。</p>';
    } else {
      toast(res.message || '删除失败', 'alert');
    }
  }

  /* ---------- 启动 ---------- */
  async function load() {
    const [recRes, repRes] = await Promise.all([IA.listInterviewRecords(), IA.getReports()]);
    records = recRes.success ? (recRes.records || []) : [];
    reports = repRes.success ? (repRes.reports || []) : [];
    if (!recRes.success) toast(recRes.message || '记录加载失败', 'alert');
    renderReports();
    renderList();
    if (records.length) openRecord(records[0].filename);
  }

  $('#recList').addEventListener('click', (e) => {
    const del = e.target.closest('[data-del]');
    if (del) { e.stopPropagation(); removeRecord(del.dataset.del, del); return; }
    const item = e.target.closest('.rec-item');
    if (item) openRecord(item.dataset.fn);
  });
  $('#openReportBtn').addEventListener('click', (e) => {
    const rec = records.find((r) => r.filename === current);
    const recDate = rec && String(rec.timestamp || '').slice(0, 8);
    const hit = reports.find((r) => String(r.timestamp || '').slice(0, 8) === recDate)
      || (rec && reports.find((r) => r.role_title === rec.role_title)) || reports[0];
    if (!hit) { e.preventDefault(); toast('未找到对应报告，请从上方报告条进入', 'alert'); return; }
    e.preventDefault();
    IA.go('summary?id=' + encodeURIComponent(hit.report_id));
  });

  if (IA.requireAuth()) load();
})();
