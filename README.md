# AI Chat Demo

一个从零实现的 AI 对话网页应用：前端负责交互与流式渲染，Node 后端负责接口代理、鉴权与限流。
**零第三方依赖**，只用 Node 原生模块和浏览器原生 API。

- 在线体验：https://ai-chat-demo.app.workbuddy.host/ （口令见下方「在线体验」）
- 源码约 750 行（`index.html` 前端 + `server.js` 后端）

## 功能

| 类别 | 实现 |
|------|------|
| 对话 | SSE 流式输出逐字上屏、`AbortController` 中断生成、多轮上下文、思考过程折叠（reasoner 模型） |
| 渲染 | 自研轻量 Markdown 渲染（标题 / 列表 / 引用 / 表格语法 / 代码块 + 语言标签 + 一键复制） |
| 安全 | API Key 服务端隔离、访客访问口令、单 IP 限流、全局每日配额、Markdown XSS 转义与协议白名单 |
| 体验 | 深浅主题切换、智能滚动（上翻历史时不被新内容打断）、首屏示例问题、系统角色设定 |

## 技术要点

**流式传输**：`fetch` + `ReadableStream.getReader()` 逐块读取 SSE 数据。网络分包会切断 JSON，所以用一个缓冲区拼接半行数据，保证解析不丢字。

**密钥隔离**：前端不接触 API Key，只与自己的后端通信，由后端携带 `Authorization` 转发到模型接口。这样即使查看网页源码也拿不到密钥。

**服务端防护**：三层拦截——口令校验（401）、单 IP 限流（429）、全局每日配额，避免公网部署后被恶意刷取额度。

**XSS 防护**：AI 返回的内容要渲染成 HTML，这是典型的注入入口。处理方式是「先转义、再解析」，链接协议只允许 `http/https`，`javascript:` 直接丢弃。

## 快速开始

```bash
# 1. 准备配置（复制示例文件，填入你的 Key）
cp config.example.json config.json

# 2. 启动
DEEPSEEK_API_KEY=sk-你的key node server.js

# Windows PowerShell：
# $env:DEEPSEEK_API_KEY="sk-你的key"; node server.js

# 3. 打开 http://localhost:3000
```

也可以直接双击 `index.html` 使用直连模式（Key 仅存于浏览器 localStorage）。

## 项目结构

```
ai-demo/
├── index.html          # 前端页面与全部交互逻辑
├── server.js           # 静态服务 + 接口代理 + 鉴权限流
├── config.example.json # 配置示例（不含密钥，可提交）
├── config.json         # 实际配置（含密钥，已在 .gitignore 中）
└── .gitignore
```

## 接口

| 接口 | 说明 |
|------|------|
| `GET /api/health` | 健康检查，返回服务状态、密钥是否就绪、是否需要口令 |
| `POST /api/chat` | 对话代理，请求头需带 `x-access-code`，支持 `stream` 开关 |

## 配置项

优先读环境变量，读不到再读 `config.json`：

| 变量 | 说明 | 默认 |
|------|------|------|
| `DEEPSEEK_API_KEY` | 模型接口密钥 | 必填 |
| `ACCESS_CODE` | 访客访问口令，留空则不校验 | 空 |
| `RATE_PER_MIN` | 单 IP 每分钟次数 | 5 |
| `RATE_PER_DAY` | 单 IP 每天次数 | 60 |
| `GLOBAL_QUOTA` | 全局每天总配额 | 200 |
| `PORT` | 服务端口 | 3000 |

## 在线体验

已部署：https://ai-chat-demo.app.workbuddy.host/

访问口令：`caihailong123`

> 公开仓库意味着口令公开。之所以仍然开放，是为了让访问者打开即可体验；
> 三层配额（5 次/分、60 次/天、全局 200 次/天）保证即使被刷取，损失也可控。
> API Key 本身不在此仓库中，只存在于部署环境的配置里。

## 说明

- 密钥相关文件（`config.json`、`key.txt`）已被 `.gitignore` 排除，不会提交。
- 建议在模型平台控制台设置月度消费上限，作为最后一道保险。
- 项目定位是学习与演示，未做用户系统、持久化存储与生产级监控。
