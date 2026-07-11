# MyOpenWeb 问题处理集合

记录开发和调试过程中遇到的问题及解决方案，方便后续查阅。

---

## 环境问题

### 1. Node.js 版本不匹配

**现象**：`npm create vite@latest` 失败，提示需要 Node `^20.19.0 || >=22.12.0`

**原因**：项目锁定 Node 18.18.0（`.nvmrc`），最新 create-vite 不兼容

**解决**：
- 使用旧版 `npx create-vite@5 . --template react-ts`
- 推荐安装 fnm 自动切换 Node 版本（详见 `fnm-node-version-management.md`）

### 2. npm install 卡住/极慢

**现象**：`npm install` 长时间无响应

**原因**：默认 npm registry 在国内访问慢

**解决**：
```bash
# 方案 A：切换镜像
npm install --registry=https://registry.npmmirror.com

# 方案 B（推荐）：使用 pnpm
pnpm install
```

### 3. Ollama 内存不足

**现象**：`Error: 500 Internal Server Error: model requires more system memory (X GiB) than is available (Y GiB)`

**原因**：模型加载需要的内存超过当前可用内存（其他程序占用过多）

**解决**：
- 关闭 Android Studio、多余的浏览器标签等吃内存的程序
- 使用更小的量化版本：`ollama run qwen3.5:4b-q4_0`
- 4B 模型约需 5GB 可用内存，7B 模型约需 8GB

### 4. Vite proxy error: ECONNREFUSED 127.0.0.1:8000

**现象**：前端终端反复出现：
```text
[vite] http proxy error: /api/config/provider
Error: connect ECONNREFUSED 127.0.0.1:8000
```

页面里可能同时显示：
```text
Provider config sync failed: HTTP 500
```

**原因**：前端 Vite 已启动，但 FastAPI 本地后端没有在 `8000` 端口监听。  
Ollama 启动只代表模型服务可用，不等于 MyOpenWeb 的本地后端已启动。

**检查**：
```bash
curl http://127.0.0.1:8000/api/health
```

如果返回连接失败，说明后端没启动。

**解决**：

Windows 推荐直接双击项目根目录的 `start-backend.bat`。

也可以在 PowerShell 里执行：
```powershell
cd D:\ai_one\MyOpenWeb
.\start-backend.bat
```

或直接使用 PowerShell 脚本：
```powershell
cd D:\ai_one\MyOpenWeb
.\scripts\dev-server.ps1
```

或者手动在 WSL 中启动：
```bash
# 首次安装后端依赖
python3 -m venv .venv
./.venv/bin/pip install -r server/requirements.txt

# 启动 FastAPI 本地后端
./.venv/bin/python -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload

# 另开一个终端启动前端
pnpm dev
```

正常情况下，`curl http://127.0.0.1:8000/api/health` 应返回：
```json
{"ok": true}
```

**注意**：必须同时启动三类服务：
- Ollama：模型服务，默认端口 `11434`
- MyOpenWeb FastAPI：本地后端，端口 `8000`
- Vite：前端开发服务器，端口 `5173`

设置页里的“测试连接”按钮会调用：
```text
POST /api/config/provider/verify
```

它会返回 provider 配置地址、实际访问地址、模型数量和错误信息。  
如果你在 WSL 中运行 FastAPI、Ollama 在 Windows 中运行，测试结果里的“实际地址”可能会显示类似 `http://172.20.0.1:11434/v1`，这是正常的 WSL 网关回退地址。

如果 Vite 在 Windows 里启动、FastAPI 在 WSL 里启动，Windows 可能无法通过 `127.0.0.1:8000` 访问 WSL。当前 `vite.config.ts` 会自动检测 WSL IP 并把 `/api` 代理到 `http://<WSL_IP>:8000`。

如需手动指定代理目标，可在启动前端前设置：
```powershell
$env:MOW_API_TARGET = "http://172.20.12.99:8000"
pnpm dev
```

---

## 手机端调试

### 5. ERR_CLEARTEXT_NOT_PERMITTED

**现象**：手机端 WebView 报 `net::ERR_CLEARTEXT_NOT_PERMITTED`

**原因**：Android 9+ 默认禁止 HTTP 明文请求

**解决**：`network_security_config.xml` 配置全局允许明文流量：
```xml
<network-security-config>
    <base-config cleartextTrafficPermitted="true">
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </base-config>
</network-security-config>
```

### 6. 手机端 API 地址是 localhost 导致无法连接

**现象**：手机端发送消息无响应，设置里 API 地址显示 `http://localhost:11434/v1`

**原因**：
- localStorage 缓存了 PC 端写入的 localhost 地址
- 手机上 localhost 指向手机自身，不是电脑

**解决**（已内置自动修复）：
- `loadSettings()` 时 `resolveApiUrl()` 自动检测页面 host，将 localhost 替换为实际 IP
- 修正后的地址会写回 localStorage
- `ChatPage.handleSend()` 发送时也会再次 resolve，双重保险
- 如自动修复未生效，手动在设置里改为 `http://192.168.137.1:11434/v1`

### 7. Ollama 不接受局域网访问

**现象**：PC 上正常，手机端请求超时或无响应

**原因**：Ollama 默认只监听 `127.0.0.1:11434`，拒绝外部连接

**解决**：设置环境变量后重启 Ollama：
```powershell
# PowerShell（永久设置）
[System.Environment]::SetEnvironmentVariable('OLLAMA_HOST', '0.0.0.0:11434', 'User')

# 然后：系统托盘 → 右键 Ollama → Quit → 重新启动 Ollama
```

### 8. 真机调试连接方式

**配置**：
1. 电脑开热点，手机连接
2. `app/build.gradle.kts` 中 `DEV_SERVER_URL` 设为 `http://192.168.137.1:5173`
3. Vite 配置 `host: true`（已配好）
4. Ollama 设置 `OLLAMA_HOST=0.0.0.0:11434`
5. H5 中 API 地址会自动适配为 `http://192.168.137.1:11434/v1`

**调试链路**：
```
手机 ──WiFi连热点──► 电脑(192.168.137.1)
  │                        ├─ Vite Dev Server (0.0.0.0:5173)
  │ WebView 加载 H5        ├─ Ollama API    (0.0.0.0:11434)
  │◄───────────────────────┘
```

---

## 模型相关

### 9. Agent 模式回复慢或没有返回

**现象**：开启设置页的“Agent 模式”后，请求明显比普通聊天慢，或者等待较久才返回。

**原因**：
- Agent v1 至少会先让模型判断是否需要工具
- 如果需要工具，会多一次“工具结果 → 模型最终回答”的请求
- 小模型有时不能稳定输出约定 JSON，后端需要等待或兜底

**解决**：
- 先用简单问题测试：`现在几点？` 或 `用计算器算 (12 + 8) * 3 / 2`
- 如果只是普通聊天，不需要工具时可以关闭“Agent 模式”
- 降低模型参数里的 Max Tokens，例如 `1024`
- 本地模型冷启动时先在 Ollama 里运行一次模型，让它加载到内存

**当前边界**：
- Agent v1 只开放 `get_current_time` 和 `calculator`
- 不支持执行系统命令
- 不支持 Dify 式复杂工作流
- 工具调用日志下一轮会补

### 10. Agent 模式直接显示 JSON 工具指令

**现象**：开启 Agent 模式后，页面直接显示：
```json
{"action":"get_current_time"}
```

或：
```json
{"action":"calculator","expression":"(12 + 8) * 3 / 2"}
```

**原因**：小模型没有严格遵守 Agent v1 约定。  
后端原本要求模型输出：
```json
{"action":"tool","tool":"calculator","input":{"expression":"(12 + 8) * 3 / 2"}}
```

但 qwen2.5:3b 这类小模型可能会把工具名直接写到 `action` 字段。旧逻辑会把它当成最终回答返回给前端。

**解决**（已修复）：
- 后端 `agent_runner` 增加兼容层
- `{"action":"get_current_time"}` 会被自动识别为时间工具调用
- `{"action":"calculator","expression":"..."}` 会被自动识别为计算器工具调用
- 工具 JSON 不应该再直接展示给用户

如果页面仍然显示 JSON：
- 重启后端或确认 `uvicorn --reload` 已完成自动重载
- 刷新前端页面
- 重新发送测试问题

推荐测试：
```text
现在几点？
```

```text
用计算器算一下 (12 + 8) * 3 / 2
```

### 11. Agent 调用了工具但页面没有显示工具摘要

**现象**：Agent 已经正常回答，但 assistant 消息下面没有显示 `Agent 调用 N 个工具`。

**原因**：
- 前端页面仍是旧构建，尚未刷新
- 后端尚未重载到支持 `agent` 元数据的版本
- 当前问题不需要工具，`toolCalls` 为空

**检查**：
```bash
curl http://127.0.0.1:8000/api/agent/runs/<run_id>
```

如果不知道 `run_id`，先用页面测试：
```text
用计算器算一下 (12 + 8) * 3 / 2
```

正常情况下，assistant 消息下方会出现：
```text
Agent 调用 1 个工具：calculator
```

**解决**：
- 等待 `uvicorn --reload` 自动重载或重启 `start-backend.bat`
- 刷新浏览器页面
- 确认设置页已经开启 Agent 模式

### 12. Memory 已添加但 Agent 没有使用

**现象**：设置页已经添加 Memory，但 Agent 回答时像没有看到。

**原因**：
- Memory 被停用了
- 当前问题和 Memory 不相关，模型没有主动使用
- 后端还没重载到包含 Memory 注入的版本
- 普通聊天模式不会走 Agent 记忆注入

**检查**：
```bash
curl http://127.0.0.1:8000/api/memories
```

确认对应记忆的 `enabled` 是 `true`。

**解决**：
- 在设置页打开 Agent 模式
- 确认 Memory 右侧状态是“启用”
- 重启后端或等待 `uvicorn --reload` 完成
- 用明确问题测试，例如：`根据你的记忆，我现在在做什么项目？`

### 13. 模型看不懂图片

**现象**：发送图片后模型回复"无法看到图片"或不理解图片内容

**原因**：使用的模型不支持多模态（如 `qwen2.5:3b` 是纯文本模型）

**解决**：
- 使用支持 vision 的模型：`qwen3.5:4b`、`llava:7b`、`moondream` 等
- `qwen3.5:4b` 推荐（最新、支持多模态、文本能力也强）

### 14. qwen3.5 输出大量 Thinking 内容

**现象**：模型回复前有很长的 `Thinking...` / `<think>...</think>` 推理过程

**原因**：qwen3.5 默认启用"思考模式"，会输出内部推理链

**解决**（已内置自动过滤）：
- 流式输出时 `filterThinking()` 自动过滤 `<think>...</think>` 标签内的内容
- 用户只看到最终回复，不看到思考过程
- 位于 `src/utils/thinking.ts`

### 15. Ollama 图片请求极慢（一直转圈）

**现象**：发送图片后 AI 长时间不回复

**原因**：OpenAI 兼容端点 `/v1/chat/completions` 处理大 base64 数据极慢

**解决**（已内置自动切换）：
- 当检测到 Ollama + 图片请求时，自动切换到原生 `/api/chat` 端点
- 原生端点用 `images` 字段传纯 base64，效率高很多
- 由 `isOllamaVisionRequest()` 自动检测，无需手动配置

---

## UI / 交互问题

### 16. 手机端按钮点击不灵敏

**现象**：按钮需要多次点击才响应

**原因**：
- 移动端浏览器 300ms 点击延迟（等待判断双击）
- 按钮尺寸太小（< 44px），触摸容易 miss
- `hover:` 状态在触摸屏上行为异常

**解决**（已修复）：
- 全局 `touch-action: manipulation` 消除延迟
- 所有按钮最小 44x44px
- 交互反馈从 `hover:` 改为 `active:`
- `-webkit-tap-highlight-color: transparent`

### 17. 无法复制聊天内容

**现象**：长按聊天文字无法选中/复制

**原因**：全局 `user-select: none` CSS 阻止了文本选择

**解决**：
- 仅对 `button`、`nav`、`[role="button"]` 设置 `user-select: none`
- 聊天区域 `.markdown-body` 设置 `user-select: text`

### 18. Sidebar 操作按钮在手机上不可用

**现象**：对话列表的导出/删除按钮在手机上看不到

**原因**：使用了 `hidden group-hover:flex`，hover 在触摸屏不触发

**解决**：操作按钮改为始终可见，不依赖 hover

---

## 构建问题

### 19. AAPT: adaptive-icon requires SDK 26

**现象**：`<adaptive-icon> elements require a sdk version of at least 26`

**原因**：`adaptive-icon` XML 放在了 `mipmap-hdpi` 目录（无版本限定）

**解决**：
- 将 `ic_launcher.xml` 移到 `mipmap-anydpi-v26/`
- `minSdk` 从 24 提升到 26（Android 8.0+，覆盖率 99%+）

### 20. TypeScript 类型错误：TextDecoderStream

**现象**：`Argument of type 'TextDecoderStream' is not assignable to parameter of type 'ReadableWritablePair<string, Uint8Array>'`

**解决**：添加类型断言：
```typescript
.pipeThrough(new TextDecoderStream() as unknown as TransformStream<Uint8Array, string>)
```

### 21. react-syntax-highlighter 包体积过大

**现象**：JS bundle 966KB，大部分来自语法高亮库

**解决**：
- 使用 Light 构建：`import { Light as SyntaxHighlighter } from 'react-syntax-highlighter/dist/esm/light'`
- 只注册常用语言（JS/TS/Python/Java/JSON 等约 15 种）
- 优化后 bundle 降至 424KB（减少 56%）

### 22. qwen3.5:4b 在 CPU 上响应极慢（2 分钟）

**现象**：发送消息后长时间转圈，看起来像没响应

**原因**：qwen3.5:4b 默认启用"思考模式"，会先生成大量 `<think>` 内容再给出回复。在无 GPU 的纯 CPU 环境下，推理一个简单 "hi" 需要 118 秒

**解决**（已内置自动关闭）：
- OpenAI 兼容端点：请求体加 `chat_template_kwargs: { enable_thinking: false }`
- Ollama 原生端点：请求体加 `think: false`
- 关闭后同样的 "hi" 从 118 秒降到 22 秒（5 倍提速）
- 在 `src/apis/chat.ts` 中自动为 Ollama 请求关闭思考模式

### 23. Ollama CORS 拒绝手机浏览器跨域请求

**现象**：手机浏览器能打开 H5 页面，但模型列表不加载、发消息无响应

**原因**：Ollama 默认只允许 `localhost` 来源的请求。手机浏览器的 origin 是 `http://192.168.137.1:5173`，不匹配 localhost，被 CORS 策略拒绝。PC 上不受影响是因为 origin 是 `http://localhost:5173`

**解决**：设置 `OLLAMA_ORIGINS` 环境变量后**重启 Ollama**：
```powershell
[System.Environment]::SetEnvironmentVariable('OLLAMA_ORIGINS', '*', 'User')
# 然后：系统托盘 → Ollama → Quit → 重新启动
```

**Ollama 所需的完整环境变量**：
```
OLLAMA_HOST = 0.0.0.0:11434     # 监听所有网卡（允许局域网访问）
OLLAMA_ORIGINS = *               # 允许所有来源的跨域请求
```

### 24. Windows 防火墙阻止手机访问电脑端口

**现象**：手机连热点后能加载 H5 页面但无法访问 Ollama API

**原因**：Windows 防火墙没有放行 11434 端口

**解决**：管理员 PowerShell 执行：
```powershell
netsh advfirewall firewall add rule name="Ollama API 11434" dir=in action=allow protocol=TCP localport=11434 profile=any
netsh advfirewall firewall add rule name="Vite Dev 5173" dir=in action=allow protocol=TCP localport=5173 profile=any
```

---

## 知识库 / 向量后端

### 25. 回答顶部出现黄色提示"知识库检索失败，本次回答未使用知识库"

**现象**：选中了知识库提问，回答正常返回，但气泡顶部有黄色警示条，且没有"引用来源"

**原因**：检索链路异常（最常见：embedding 模型服务不可达，如 Ollama 未启动或 `bge-m3` 未拉取；pgvector 模式下还可能是 PostgreSQL 连不上）。系统设计为检索失败时**降级为普通回答而不是报 502**，警示条括号里带具体原因

**解决**：
- 按警示条括号里的原因排查：`ollama pull bge-m3`、确认 Ollama 已启动、设置页"测试连接"
- pgvector 模式：确认 PG 容器在跑（`docker compose ps`）、`MYOPENWEB_PG_DSN` 正确
- 修复后重新提问即可，无需重启后端

### 26. 切换 pgvector 后端后检索结果为空

**现象**：设置 `MYOPENWEB_VECTOR_BACKEND=pgvector` 重启后，知识库问答全部拒答，知识库页分块数显示 0

**原因**：切换后端不迁移数据——SQLite 里的旧向量不会自动搬到 PostgreSQL，chunks 需要重建

**解决**：
- 知识库页对每个库点「建立/重建索引」，向量会写入 PG
- 切回 SQLite 同理（原 SQLite 向量还在，无需重建）

### 27. pgvector 启动报错 MYOPENWEB_PG_DSN / psycopg 缺失

**现象**：`RuntimeError: MYOPENWEB_VECTOR_BACKEND=pgvector 需要同时设置 MYOPENWEB_PG_DSN`，或 `pgvector 后端需要 psycopg`

**解决**：
```bash
# 本地裸跑：装驱动 + 给 DSN
./.venv/bin/pip install -r server/requirements-pgvector.txt
export MYOPENWEB_VECTOR_BACKEND=pgvector
export MYOPENWEB_PG_DSN=postgresql://myopenweb:myopenweb@localhost:5432/myopenweb

# Docker：一条命令带起 PG（镜像已内置驱动与默认 DSN）
MYOPENWEB_VECTOR_BACKEND=pgvector docker compose --profile pgvector up -d --build
```

首连自动执行 `CREATE EXTENSION vector` 并建表，要求 PG 侧安装了 pgvector 扩展（`pgvector/pgvector:pg16` 镜像自带）。

---

## Git 操作

### 28. PowerShell Heredoc 语法报错

**现象**：用 `<<'EOF'` 写多行 commit message 时 PowerShell 报 `ParserError`

**原因**：PowerShell 不支持 bash 的 heredoc 语法

**解决**：使用多个 `-m` 参数：
```powershell
git commit -m "subject line" -m "body line 1" -m "body line 2"
```
