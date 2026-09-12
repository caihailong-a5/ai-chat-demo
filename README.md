# AI 接口调用网页 Demo

一个最小可用的 AI 网页 demo：网页 → JS → AI 接口 → 流式返回 → 渲染上屏。
零依赖，纯原生实现，代码带详细中文注释。

## 文件说明

| 文件 | 作用 |
|------|------|
| `index.html` | 前端页面 + 全部 JS 逻辑（约 200 行，可直接读） |
| `server.js` | Node 原生后端：静态服务 + AI 接口代理（零依赖） |

## 两种运行方式

### 方式一：代理模式（推荐，Key 不暴露）

```bash
# macOS / Linux
DEEPSEEK_API_KEY=sk-你的key node server.js

# Windows PowerShell
$env:DEEPSEEK_API_KEY="sk-你的key"; node server.js
```

然后浏览器打开 http://localhost:3000

此模式下页面会自动隐藏 Key 输入框（因为根本不需要），顶部显示绿色的「代理模式」。

### 方式二：直连模式（双击 index.html 即用）

直接双击 `index.html`，在页面顶部填 Key。Key 只存在浏览器的 `localStorage` 里，不会写进任何文件、不会上传到任何地方。

> 注意：`file://` 协议下部分浏览器会因 CORS 拦截请求，如果报错，用方式一。

## 核心逻辑（面试/复盘用四句话讲清）

1. **收集**：`messages` 数组维护完整上下文，每轮把用户的话 `push` 进去 —— 多轮对话全靠它，AI 本身是无状态的。
2. **发送**：`fetch(url, { method:'POST', headers:{Authorization}, body: JSON.stringify({model, messages, stream:true}) })`
3. **接收**：`stream:true` 时服务端按 SSE 格式一行行推数据，用 `res.body.getReader()` 边读边拼，遇到网络分包要用 `buffer` 存住不完整的最后一行。
4. **渲染**：解析出 `delta.content` 追加到页面，同时把完整回答 `push` 回 `messages`，下一轮才有记忆。

## 面试官大概率会追问的点

- **为什么不直接在前端调 AI 接口？**
  因为 Key 会随网页源码泄露（F12 就能看到），被人刷爆额度。正解是前端调自己的后端，后端带 Key 转发。本项目 `server.js` 就是标准答案。

- **为什么要用流式（stream）？**
  大模型生成一条回答要几秒到几十秒。非流式会让页面干等、用户以为卡死；流式可以做到「边生成边显示」，体验差距巨大。

- **为什么要 `async/await`？**
  网络请求是异步的，不用 `await` 拿到的会是一个 Promise 而不是数据。

- **多轮对话是怎么实现的？**
  模型本身不记上下文，每次请求都要把完整历史 `messages` 一起发过去。所以上下文越长，消耗的 token 越多、费用越高。

- **错误怎么处理？**
  不能只看网络通不通，必须判断 `res.ok` / `res.status`，并把上游返回的原始错误信息透传到前端（本项目已实现）。

## 线上部署

已发布：https://ai-chat-demo.app.workbuddy.host/

**访问口令：`caihailong123`**（在页面顶部「访问口令」框里填一次，浏览器会记住）

> 换口令后，之前浏览器里缓存的旧口令会失效；页面检测到 401 会自动清空并提示重填，无需手动清理。

### 三道防线（server.js 内实现）

| 防线 | 作用 | 默认值 |
|------|------|--------|
| 访问口令 | 请求头必须带正确的 `x-access-code` | `caihailong123` |
| 频率限制 | 单 IP 每分钟 / 每天上限 | 5 次/分，60 次/天 |
| 全局配额 | 所有 IP 合计每天封顶 | 200 次/天 |

超出任一限制会返回 429 和可读取的提示文案。参数全在 `config.json` 里改。

### 配置方式

- **线上**：改 `config.json`（无法注入环境变量，只能走文件）
- **本地**：用环境变量，优先级更高

```bash
DEEPSEEK_API_KEY=sk-xxx ACCESS_CODE=demo2026 node server.js
```

## 安全提醒

- `config.json` 和 `key.txt` 已在 `.gitignore` 里，**别把整个目录推到公开 GitHub**。
- 建议去 DeepSeek 控制台设置月度消费上限，作为最后一道保险。
- Key 若已泄露过，去控制台删除并重新生成。
