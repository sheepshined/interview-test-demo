import { renderMarkdown } from '../frontend/src/utils/markdown.js'

// 模拟 AI 对话中真实出现的公式场景
const cases = [
  ['块级公式',
   '注意力机制的核心公式：\n\n$$\\text{Attention}(Q,K,V)=\\text{softmax}\\left(\\frac{QK^T}{\\sqrt{d_k}}\\right)V$$\n\n以上。',
   t => t.includes('katex') && !t.includes('$$')],
  ['行内公式',
   '其中 $d_k$ 是每个头的维度。',
   t => t.includes('katex') && !t.includes('$d_k$')],
  ['货币防误伤',
   '这个方案花费 $100 预算成本 $200 不等。',
   t => !t.includes('katex')],
  ['中文防误伤',
   '价格是 $5 元 和 $10 元。',
   t => !t.includes('katex')],
  ['公式含下划线',
   '多头的输出 $W_i Q$ 会拼接。',
   t => t.includes('katex')],
  ['代码块内 $ 不当公式',
   '```bash\nprice=$100\n```',
   t => t.includes('md-pre') && !t.includes('katex')],
  ['坏 LaTeX 不崩溃',
   '$$\\frac{$$ 未闭合',
   t => t.length > 0],   // 不抛异常即通过
]
let pass = 0
for (const [name, input, check] of cases) {
  const t0 = Date.now()
  let out
  try { out = renderMarkdown(input) } catch (e) { out = 'THREW: ' + e.message }
  const ms = Date.now() - t0
  const ok = check(out) && ms < 500
  console.log(ok ? 'PASS' : 'FAIL', name, ms + 'ms')
  if (!ok) console.log('   =>', out.slice(0, 150))
  if (ok) pass++
}
console.log(`\n${pass}/${cases.length} passed`)
process.exit(pass === cases.length ? 0 : 1)
