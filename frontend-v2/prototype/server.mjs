/* ============================================================
   墨卷档案 · 开发服务器
   静态托管 prototype/ + 把 /api、/ws 反向代理到 FastAPI(127.0.0.1:8000)
   ——与原 Vite 代理等价，后端零改动。零依赖：node server.mjs
   ============================================================ */
import http from 'node:http';
import net from 'node:net';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = 4173;
const BACKEND_HOST = '127.0.0.1';
const BACKEND_PORT = 8000;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.md': 'text/markdown; charset=utf-8',
};

/* ---------- 静态文件 ---------- */
function serveStatic(req, res) {
  let urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
  if (urlPath.endsWith('/')) urlPath += 'index.html';
  const filePath = path.normalize(path.join(__dirname, urlPath));
  if (!filePath.startsWith(__dirname)) {
    res.writeHead(403).end('Forbidden');
    return;
  }
  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end('404 Not Found');
      return;
    }
    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, {
      'Content-Type': MIME[ext] || 'application/octet-stream',
      'Cache-Control': 'no-cache', // 原型开发期禁缓存，避免改了看不到
    });
    res.end(data);
  });
}

/* ---------- /api 反向代理 ---------- */
function proxyApi(req, res) {
  const opts = {
    host: BACKEND_HOST,
    port: BACKEND_PORT,
    path: req.url,
    method: req.method,
    headers: { ...req.headers, host: `${BACKEND_HOST}:${BACKEND_PORT}` },
  };
  const upstream = http.request(opts, (ur) => {
    res.writeHead(ur.statusCode, ur.headers);
    ur.pipe(res);
  });
  upstream.on('error', () => {
    res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ success: false, message: '无法连接后端服务，请先启动 FastAPI (127.0.0.1:8000)' }));
  });
  req.pipe(upstream);
}

/* ---------- /ws WebSocket 隧道（握手后原样转发字节流） ---------- */
function proxyWs(req, socket, head) {
  const upstream = net.connect(BACKEND_PORT, BACKEND_HOST, () => {
    const lines = [`${req.method} ${req.url} HTTP/1.1`];
    for (let i = 0; i < req.rawHeaders.length; i += 2) {
      if (req.rawHeaders[i].toLowerCase() === 'host') continue;
      lines.push(`${req.rawHeaders[i]}: ${req.rawHeaders[i + 1]}`);
    }
    lines.push(`Host: ${BACKEND_HOST}:${BACKEND_PORT}`);
    upstream.write(lines.join('\r\n') + '\r\n\r\n');
    if (head && head.length) upstream.write(head);
    socket.pipe(upstream);
    upstream.pipe(socket);
  });
  const bail = () => { try { socket.destroy(); } catch (_) {} try { upstream.destroy(); } catch (_) {} };
  upstream.on('error', bail);
  socket.on('error', bail);
}

const server = http.createServer((req, res) => {
  if (req.url.startsWith('/api/') || req.url.startsWith('/ws')) proxyApi(req, res);
  else serveStatic(req, res);
});
server.on('upgrade', proxyWs);

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[interview-studio] http://127.0.0.1:${PORT}  (api/ws → ${BACKEND_HOST}:${BACKEND_PORT})`);
});
