/**
 * 轻量安全 Markdown 渲染 (零依赖)。
 *
 * 支持: 代码围栏、行内代码、标题、分割线、有序/无序列表、引用、
 * 加粗、斜体、链接、GFM 表格、段落与换行。
 * 先做 HTML 转义, 再生成标签, 链接仅允许 http(s)/相对路径, 防 XSS。
 *
 * 代码块/行内代码在解析期间用带唯一前缀的 ASCII 哨兵占位,
 * 避免内部符号被二次解析; 哨兵前缀足够特殊, 正常文本不会冲突。
 */

const BLOCK_TOKEN = 'MDXVBLOCK'   // 代码围栏占位前缀:  MDXVBLOCK0
const CODE_TOKEN = 'MDXVVCODE'    // 行内代码占位前缀:  MDXVVCODE0
const BLOCK_LINE_RE = new RegExp(`^${BLOCK_TOKEN}(\\d+)$`)
const BLOCK_ANY_RE = new RegExp(`${BLOCK_TOKEN}\\d+`)

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function safeUrl(url) {
  const u = (url || '').trim()
  if (/^(https?:|\/|#)/i.test(u)) return u
  return ''
}

function renderInline(raw) {
  let t = escapeHtml(raw)
  const codes = []
  // 行内代码: 原样保留, 不解析内部符号 (哨兵占位)
  t = t.replace(/`([^`\n]+)`/g, (_, code) => {
    codes.push(`<code class="md-code-inline">${code}</code>`)
    return ` ${CODE_TOKEN}${codes.length - 1} `
  })
  // 链接 [text](url)
  t = t.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, text, url) => {
    const href = safeUrl(url)
    return href ? `<a href="${href}" target="_blank" rel="noopener noreferrer" class="md-link">${text}</a>` : text
  })
  // 加粗 **x** / __x__
  t = t.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  t = t.replace(/__([^_]+)__/g, '<strong>$1</strong>')
  // 斜体 *x* / _x_
  t = t.replace(/(^|[\s(])\*([^*\n]+)\*(?=$|[\s).,!?])/g, '$1<em>$2</em>')
  t = t.replace(/(^|[\s(])_([^_\n]+)_(?=$|[\s).,!?])/g, '$1<em>$2</em>')
  // 还原行内代码
  t = t.replace(new RegExp(` ${CODE_TOKEN}(\\d+) `, 'g'), (m, idx) => codes[Number(idx)] || m)
  return t
}

function isHr(line) {
  return /^\s{0,3}(?:-\s*-{2,}|\*\s*\*{2,}|_\s*_{2,})\s*$/.test(line)
}

function isTableSep(line) {
  const cells = line.trim().replace(/^\||\|$/g, '').split('|')
  return cells.length > 0 && cells.every(c => /^\s*:?-{1,}:?\s*$/.test(c))
}

function splitTableRow(line) {
  return line.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim())
}

function blockIndex(line) {
  const m = line.match(BLOCK_LINE_RE)
  return m ? Number(m[1]) : -1
}

export function renderMarkdown(text) {
  if (!text) return ''
  const src = String(text).replace(/\r\n?/g, '\n')

  // 1. 提取代码围栏为哨兵占位 (整块 HTML, 不再参与行级解析)
  const blocks = []
  const protectedSrc = src.replace(/```([^\n]*)\n([\s\S]*?)```/g, (m, lang, code) => {
    blocks.push(
      `<pre class="md-pre"><code class="md-code-block">${escapeHtml(code.replace(/\n$/, ''))}</code></pre>`
    )
    return ` ${BLOCK_TOKEN}${blocks.length - 1} `
  })

  const lines = protectedSrc.split('\n')
  const html = []
  let i = 0

  const pushParagraph = (buf) => {
    const body = buf.map(renderInline).join('<br>')
    if (body.trim()) html.push(`<p class="md-p">${body}</p>`)
  }

  while (i < lines.length) {
    const line = lines[i]
    const iBefore = i

    if (!line.trim()) { i++; continue }

    // 代码围栏占位: 还原为整块 HTML (允许两侧有空白)
    const bidx = blockIndex(line.trim())
    if (bidx >= 0) {
      if (blocks[bidx]) html.push(blocks[bidx])
      i++
      continue
    }

    if (isHr(line)) {
      html.push('<hr class="md-hr">')
      i++
      continue
    }

    // 标题
    const heading = line.match(/^(#{1,6})\s+(.*)$/)
    if (heading) {
      const level = Math.min(heading[1].length, 4)
      html.push(`<h${level} class="md-h md-h${level}">${renderInline(heading[2])}</h${level}>`)
      i++
      continue
    }

    // 引用 (连续 > 行)
    if (/^\s*>\s?/.test(line)) {
      const quote = []
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
        quote.push(lines[i].replace(/^\s*>\s?/, ''))
        i++
      }
      html.push(`<blockquote class="md-quote">${renderInline(quote.join('<br>'))}</blockquote>`)
      continue
    }

    // 无序列表
    if (/^\s*[-*•]\s+/.test(line)) {
      const items = []
      while (i < lines.length && /^\s*[-*•]\s+/.test(lines[i])) {
        items.push(`<li>${renderInline(lines[i].replace(/^\s*[-*•]\s+/, ''))}</li>`)
        i++
      }
      html.push(`<ul class="md-ul">${items.join('')}</ul>`)
      continue
    }

    // 有序列表
    if (/^\s*\d+[.)]\s+/.test(line)) {
      const items = []
      while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i])) {
        items.push(`<li>${renderInline(lines[i].replace(/^\s*\d+[.)]\s+/, ''))}</li>`)
        i++
      }
      html.push(`<ol class="md-ol">${items.join('')}</ol>`)
      continue
    }

    // 表格 (表头 | 分隔 | 数据行)
    if (line.includes('|') && lines[i + 1] && isTableSep(lines[i + 1])) {
      const header = splitTableRow(line)
      i += 2
      const rows = []
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) {
        rows.push(splitTableRow(lines[i]))
        i++
      }
      const thead = `<thead><tr>${header.map(h => `<th>${renderInline(h)}</th>`).join('')}</tr></thead>`
      const tbody = `<tbody>${rows
        .map(r => `<tr>${header.map((_, c) => `<td>${renderInline(r[c] || '')}</td>`).join('')}</tr>`)
        .join('')}</tbody>`
      html.push(`<table class="md-table">${thead}${tbody}</table>`)
      continue
    }

    // 普通段落 (连续非空、非块级行)
    const para = []
    while (
      i < lines.length &&
      lines[i].trim() &&
      !BLOCK_ANY_RE.test(lines[i]) &&
      !/^(#{1,6})\s+/.test(lines[i]) &&
      !/^\s*>/.test(lines[i]) &&
      !/^\s*[-*•]\s+/.test(lines[i]) &&
      !/^\s*\d+[.)]\s+/.test(lines[i]) &&
      !isHr(lines[i])
    ) {
      para.push(lines[i])
      i++
    }
    pushParagraph(para)

    // 防御性兜底: 任何未知行型都强制前进, 杜绝渲染器死循环卡死页面
    if (i === iBefore) i++
  }

  return html.join('\n')
}
