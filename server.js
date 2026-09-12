// ============================================================
//  AI 接口代理服务（含公网防护）
//  ------------------------------------------------------------
//  为什么需要后端？
//  把 API Key 写在前端 JS 里，任何人 F12 就能看到并刷爆你的额度。
//  正确架构：浏览器 → 你的后端（带 Key）→ AI 厂商
//
//  为什么需要防护？
//  服务一旦部署到公网，/api/chat 全世界都能调用，
//  别人不需要拿到你的 Key，也能借你的接口烧你的钱。
//  所以这里加了三道防线：访问口令 + 频率限制 + 每日配额。
//
//  零依赖，只用 Node 自带模块，Node 18+ 可直接运行。
// ============================================================

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || 3000;   // 云平台会注入自己的 PORT
const UPSTREAM = 'https://api.deepseek.com/chat/completions';

// ---------- 配置来源：环境变量优先，其次同目录 config.json ----------
// 线上部署时无法注入环境变量，所以把配置写进 config.json（记得加 .gitignore）
let fileCfg = {};
try {
  fileCfg = JSON.parse(fs.readFileSync(path.join(__dirname, 'config.json'), 'utf8'));
} catch (e) { /* 没有 config.json 就全走环境变量 */ }

function cfg(envName, fileKey, dflt) {
  const v = process.env[envName] !== undefined ? process.env[envName] : fileCfg[fileKey];
  return (v === undefined || v === '') ? dflt : v;
}

const ACCESS_CODE  = String(cfg('ACCESS_CODE',  'accessCode',  '')).trim();   // 留空 = 不校验
const RATE_PER_MIN = Number(cfg('RATE_PER_MIN', 'ratePerMin',  5));           // 单 IP 每分钟次数
const RATE_PER_DAY = Number(cfg('RATE_PER_DAY', 'ratePerDay',  60));          // 单 IP 每天次数
const GLOBAL_QUOTA = Number(cfg('GLOBAL_QUOTA', 'globalQuota', 200));         // 全局每天总配额

// ---------- Key 读取：环境变量 → config.json → key.txt ----------
function getApiKey() {
  const fromEnv = String(cfg('DEEPSEEK_API_KEY', 'apiKey', '')).trim();
  if (fromEnv) return fromEnv;
  const p = path.join(__dirname, 'key.txt');
  if (fs.existsSync(p)) return fs.readFileSync(p, 'utf8').trim();
  return '';
}

// ============================================================
//  限流实现：滑动计数，Map 存在内存里（重启即清零，够 demo 用）
//  返回 0 = 通过；返回 >0 = 被拦，值为还需等待的秒数
// ============================================================
const ipMinHits = new Map();
const ipDayHits = new Map();
let globalDay = { t: Date.now(), n: 0 };

function hit(map, key, limit, windowMs) {
  const now = Date.now();
  let rec = map.get(key);
  if (!rec || now - rec.t > windowMs) rec = { t: now, n: 0 };
  rec.n += 1;
  map.set(key, rec);
  return rec.n > limit ? Math.ceil((windowMs - (now - rec.t)) / 1000) : 0;
}

function getIp(req) {
  const fwd = req.headers['x-forwarded-for'];
  if (fwd) return fwd.split(',')[0].trim();
  return (req.socket.remoteAddress || 'unknown').replace('::ffff:', '');
}

function deny(res, status, msg) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify({ error: msg }));
}

const server = http.createServer(async (req, res) => {
  // ---- 健康检查：前端靠它判断"后端在不在、要不要填口令" ----
  if (req.url === '/api/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({
      ok: true,
      keyReady: !!getApiKey(),
      needCode: !!ACCESS_CODE
    }));
  }

  // ---- 聊天代理 ----
  if (req.url === '/api/chat' && req.method === 'POST') {
    const key = getApiKey();
    if (!key) return deny(res, 500, '服务端未配置 DEEPSEEK_API_KEY');

    // 防线 1：访问口令
    if (ACCESS_CODE && req.headers['x-access-code'] !== ACCESS_CODE) {
      return deny(res, 401, '访问口令不正确');
    }

    const ip = getIp(req);

    // 防线 2：频率限制（单 IP 分钟级 + 天级）
    const wMin = hit(ipMinHits, ip, RATE_PER_MIN, 60 * 1000);
    if (wMin) return deny(res, 429, '请求太频繁，请 ' + wMin + ' 秒后再试');
    const wDay = hit(ipDayHits, ip, RATE_PER_DAY, 24 * 60 * 60 * 1000);
    if (wDay) return deny(res, 429, '今日个人额度已用完，请明天再来');

    // 防线 3：全局每日配额（最后一道保险）
    const now = Date.now();
    if (now - globalDay.t > 24 * 60 * 60 * 1000) globalDay = { t: now, n: 0 };
    globalDay.n += 1;
    if (globalDay.n > GLOBAL_QUOTA) {
      return deny(res, 429, '服务今日总配额已用完，请明天再来');
    }

    let body = '';
    for await (const chunk of req) body += chunk;

    try {
      const upstream = await fetch(UPSTREAM, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + key
        },
        body
      });

      res.writeHead(upstream.status, {
        'Content-Type': upstream.headers.get('content-type') || 'application/json',
        'Cache-Control': 'no-cache'
      });

      // 流式原样透传，边收边发，不做缓冲
      const reader = upstream.body.getReader();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        res.write(value);
      }
      res.end();
    } catch (e) {
      res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ error: '请求上游失败: ' + e.message }));
    }
    return;
  }

  // ---- 静态文件 ----
  const filePath = req.url === '/' ? '/index.html' : req.url.split('?')[0];
  const full = path.join(__dirname, path.normalize(filePath).replace(/^(\.\.[\/\\])+/, ''));
  fs.readFile(full, (err, data) => {
    if (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      return res.end('404 Not Found');
    }
    const ext = path.extname(full);
    const types = {
      '.html': 'text/html; charset=utf-8',
      '.js': 'text/javascript; charset=utf-8',
      '.css': 'text/css; charset=utf-8'
    };
    res.writeHead(200, { 'Content-Type': types[ext] || 'application/octet-stream' });
    res.end(data);
  });
});

server.listen(PORT, () => {
  console.log('服务已启动: http://localhost:' + PORT);
  console.log('Key: ' + (getApiKey() ? '已配置' : '未配置'));
  console.log('口令防护: ' + (ACCESS_CODE ? '开启' : '关闭（公网部署务必开启）'));
  console.log('限额: 单IP ' + RATE_PER_MIN + '次/分, ' + RATE_PER_DAY + '次/天 | 全局 ' + GLOBAL_QUOTA + '次/天');
});
