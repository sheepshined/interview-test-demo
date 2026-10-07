/* 面试全链路 E2E（直连 8000）：config → 开场白 → Q1/Q2/Q3 作答 → hint → 追问 → end → report */
import http from 'node:http';
import crypto from 'node:crypto';

const PORT = 8000;
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);

function wsFrame(payload) {
  const data = Buffer.from(payload, 'utf8');
  const mask = crypto.randomBytes(4);
  let header;
  if (data.length < 126) header = Buffer.from([0x81, 0x80 | data.length]);
  else if (data.length < 65536) { header = Buffer.alloc(4); header[0] = 0x81; header[1] = 0x80 | 126; header.writeUInt16BE(data.length, 2); }
  else { header = Buffer.alloc(10); header[0] = 0x81; header[1] = 0x80 | 127; header.writeBigUInt64BE(BigInt(data.length), 2); }
  const masked = Buffer.alloc(data.length);
  for (let i = 0; i < data.length; i++) masked[i] = data[i] ^ mask[i % 4];
  return Buffer.concat([header, mask, masked]);
}
function login() {
  return new Promise((resolve, reject) => {
    const req = http.request(`http://127.0.0.1:${PORT}/api/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' } }, (res) => {
      let b = ''; res.on('data', (c) => b += c); res.on('end', () => { const d = JSON.parse(b); d.success ? resolve(d.token) : reject(new Error(d.message)); });
    });
    req.on('error', reject); req.write(JSON.stringify({ username: 'admin', password: '123123' })); req.end();
  });
}

const ANSWERS = {
  1: '我做 RAG 落地时评估分三类指标：忠实度看回答是否都有上下文支撑，切题度看是否回答了问题，召回率看必要信息是否被检索回来。评测集用真实 query 加人工标注的标准答案和支撑段落，50 条起步，用 LLM 当裁判打分再抽 20% 人工校准，保证和线上口径一致。',
  2: '文档先按语义边界分块，长文档用父文档策略：子块建向量索引、父块作为返回单元，这样小块负责精准匹配、父块保证上下文完整。召回用 BM25 加向量双路各取 Top20，RRF 按排名融合。重排用交叉编码器对候选精排，因为双塔相似度是粗粒度的，重排后 Top3 命中率明显更稳。',
  3: '部署上模型服务做并发限制和排队，检索结果按 query 归一化后缓存，embedding 走批处理降低调用次数；成本按输入输出 token 分别估算，每个接口设超时和降级路径，报告生成用强模型、出题评分用快模型来分层控制成本。',
};

let q = 0, asked = false, hintUsed = false, followupSeen = false;
const seen = new Set();

function send(socket, obj) { socket.write(wsFrame(JSON.stringify(obj))); }

function handle(msg, socket) {
  if (msg.type !== 'stream_chunk' && msg.type !== 'stream_start') seen.add(msg.type);
  switch (msg.type) {
    case 'config_ok': log('✓ config_ok'); break;
    case 'stream_start':
      if (msg.question_index) q = msg.question_index;
      if (msg.stream_type === 'followup') followupSeen = true;
      log('▶', msg.stream_type, msg.question_index ? 'Q' + msg.question_index : '');
      break;
    case 'stream_end':
      if (msg.stream_type === 'question' || msg.stream_type === 'followup') {
        asked = true;
        const idx = Math.min(q, 3);
        setTimeout(() => { log('→ 作答 Q' + q); send(socket, { type: 'answer', content: ANSWERS[idx] }); }, 1000);
      }
      break;
    case 'decision':
      log('✓ decision:', msg.action, '—', (msg.reason || '').slice(0, 36));
      break;
    case 'hint': log('✓ hint', msg.hint_level, (msg.content || '').slice(0, 24)); break;
    case 'interview_ended':
      log('✓✓ interview_ended answered=' + msg.answered_count + '/' + msg.total_count);
      setTimeout(() => { log('→ 请求报告'); send(socket, { type: 'report' }); }, 800);
      break;
    case 'report_ready':
      log('✓✓✓ report_ready', msg.report_id, '| 共收到消息类型:', [...seen].join(','));
      socket.destroy(); process.exit(0);
      break;
    case 'report_ready_placeholder': break;
    case 'status': log('· status:', (msg.content || '').slice(0, 30)); break;
    case 'error': log('✗ error:', msg.content); process.exit(1);
  }
}

const token = await login();
log('✓ login');
const key = crypto.randomBytes(16).toString('base64');
const req = http.request({
  host: '127.0.0.1', port: PORT, path: '/ws/chat?token=' + encodeURIComponent(token),
  headers: { Connection: 'Upgrade', Upgrade: 'websocket', 'Sec-WebSocket-Key': key, 'Sec-WebSocket-Version': '13' },
});
req.on('upgrade', (res, socket) => {
  log('✓ ws connected');
  send(socket, { type: 'config', role: 'llm_app', question_count: 3, difficulty: 2, resume_context: '', resume_skills: [] });
  let buf = Buffer.alloc(0);
  const T = setTimeout(() => { log('✗ OVERALL TIMEOUT'); process.exit(1); }, 480000);
  const hintTimer = setTimeout(() => {
    if (!hintUsed && asked) { hintUsed = true; log('→ 请求提示'); send(socket, { type: 'hint' }); }
  }, 25000);
  socket.on('data', (chunk) => {
    buf = Buffer.concat([buf, chunk]);
    for (;;) {
      if (buf.length < 2) break;
      const op = buf[0] & 0x0f;
      let len = buf[1] & 0x7f, off = 2;
      if (len === 126) { if (buf.length < 4) break; len = buf.readUInt16BE(2); off = 4; }
      else if (len === 127) { if (buf.length < 10) break; len = Number(buf.readBigUInt64BE(2)); off = 10; }
      if (buf.length < off + len) break;
      const payload = buf.slice(off, off + len);
      buf = buf.slice(off + len);
      if (op === 0x9) {
        const pm = crypto.randomBytes(4);
        const mk = Buffer.alloc(len);
        for (let i = 0; i < len; i++) mk[i] = payload[i] ^ pm[i % 4];
        socket.write(Buffer.concat([Buffer.from([0x8a, 0x80 | len]), pm, mk]));
        continue;
      }
      if (op !== 1) continue;
      let msg; try { msg = JSON.parse(payload.toString('utf8')); } catch (_) { continue; }
      handle(msg, socket);
    }
  });
  socket.on('close', () => { log('socket closed'); });
});
req.on('response', (r) => { console.error('handshake rejected', r.statusCode); process.exit(1); });
req.end();
