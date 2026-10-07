/* ============================================================
   墨卷档案 · 安全 Markdown 渲染（精简版）
   先整体 HTML 转义再生成标签（防 XSS）；支持标题/列表/加粗/
   行内代码/代码围栏/引用/段落；[[双链]] 渲染为可点样式。
   ============================================================ */
(() => {
  'use strict';

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function inline(s) {
    let out = esc(s);
    out = out.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
    out = out.replace(/`([^`]+)`/g, '<code>$1</code>');
    out = out.replace(/\[\[([^\]]+)\]\]/g, '<span class="wikilink" data-wiki="$1">$1</span>');
    return out;
  }

  function renderMd(src) {
    const lines = String(src || '').replace(/\r\n/g, '\n').split('\n');
    let html = '', inUl = false, inOl = false, inQuote = false, inCode = false, para = [];

    const closePara = () => { if (para.length) { html += '<p>' + inline(para.join(' ')) + '</p>'; para = []; } };
    const closeUl = () => { if (inUl) { html += '</ul>'; inUl = false; } };
    const closeOl = () => { if (inOl) { html += '</ol>'; inOl = false; } };
    const closeQuote = () => { if (inQuote) { html += '</blockquote>'; inQuote = false; } };
    const closeAll = () => { closePara(); closeUl(); closeOl(); closeQuote(); };

    for (const raw of lines) {
      const line = raw.trimEnd();
      if (line.trim().startsWith('```')) {
        closeAll();
        html += inCode ? '</pre>' : '<pre><code>';
        inCode = !inCode;
        continue;
      }
      if (inCode) { html += esc(raw) + '\n'; continue; }

      if (/^###\s+/.test(line)) { closeAll(); html += '<h3>' + inline(line.replace(/^###\s+/, '')) + '</h3>'; continue; }
      if (/^##\s+/.test(line)) { closeAll(); html += '<h2>' + inline(line.replace(/^##\s+/, '')) + '</h2>'; continue; }
      if (/^#\s+/.test(line)) { closeAll(); html += '<h2>' + inline(line.replace(/^#\s+/, '')) + '</h2>'; continue; }
      if (/^---+$/.test(line.trim())) { closeAll(); html += '<hr />'; continue; }
      if (/^>\s?/.test(line)) {
        closePara(); closeUl(); closeOl();
        if (!inQuote) { html += '<blockquote>'; inQuote = true; }
        html += '<p>' + inline(line.replace(/^>\s?/, '')) + '</p>';
        continue;
      }
      closeQuote();
      if (/^[-*]\s+/.test(line)) {
        closePara(); closeOl();
        if (!inUl) { html += '<ul>'; inUl = true; }
        html += '<li>' + inline(line.replace(/^[-*]\s+/, '')) + '</li>';
        continue;
      }
      if (/^\d+[.、]\s*/.test(line)) {
        closePara(); closeUl();
        if (!inOl) { html += '<ol>'; inOl = true; }
        html += '<li>' + inline(line.replace(/^\d+[.、]\s*/, '')) + '</li>';
        continue;
      }
      if (!line.trim()) { closePara(); closeUl(); closeOl(); continue; }
      closeUl(); closeOl();
      para.push(line.trim());
    }
    closeAll();
    if (inCode) html += '</code></pre>';
    return html;
  }

  window.renderMd = renderMd;
})();
