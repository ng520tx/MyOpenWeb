# MyOpenWeb 项目架构文档

## 项目定位

基于 Open WebUI 拆解的个人版 AI App 骨架，目标是做成「企业研发/运维 AI Copilot 工作台」的求职作品。  
当前架构已经从“前端直连模型服务”升级为：

- React H5 聊天页
- Android WebView 壳
- FastAPI 本地后端
- SQLite 对话/配置/Agent 日志/记忆/文件/知识库持久化
- 原生 STT/TTS/文件桥接
- Ollama / OpenAI Compatible 模型接入
- 文件落盘 + 文本抽取（txt/md/pdf/docx，可选 PaddleOCR）
- 自研 RAG 知识库（切片 + 向量化 + 混合检索 BM25/向量 RRF 融合 + 可选 bge-reranker 重排 + 引用来源 + 无答案拒答）
- 检索质量评测（40 条 QA，Hit@K / MRR / 延迟参数对照，`server/eval/`）
- 研发/运维 Agent 工具（日志分析、Git diff 摘要、工单总结、测试用例生成、知识库检索）
- pytest 单元测试 + GitHub Actions CI + Docker 一键部署

当前阶段的目标不是做成 Dify 那样的工作流平台，而是把 RAG 知识库和真实研发/运维 Agent 工具全部自研落地，便于面试讲清底层。RAG / Agent 功能模块的产品化说明见 `docs/rag-agent-copilot.md`。

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 前端构建 | Vite | 5.x |
| 前端框架 | React | 18.x |
| 前端语言 | TypeScript | 5.x |
| 样式 | Tailwind CSS | 3.x |
| 状态管理 | Zustand | 4.x |
| Markdown | react-markdown + remark-gfm | 9.x |
| 代码高亮 | react-syntax-highlighter | 16.x |
| 流式解析 | eventsource-parser | 1.x |
| 本地后端 | FastAPI | 0.136.x |
| 后端语言 | Python | 3.12.x |
| 数据库 | SQLite | Python 内置 sqlite3（向量存 JSON，BM25 用 FTS5） |
| Rerank（可选） | sentence-transformers CrossEncoder | bge-reranker-base |
| 测试 / CI | pytest + GitHub Actions | 见 `.github/workflows/ci.yml` |
| 部署 | Docker 多阶段构建 + docker-compose | 见 `Dockerfile` |
| Android | Kotlin + WebView | API 26+ |
| 包管理 | pnpm | 10.x |
| Node | Node.js | 18.18.0（见 `.nvmrc`） |

## 目录结构

```text
MyOpenWeb/
├── docs/
│   ├── project-architecture.md
│   ├── troubleshooting.md
│   └── fnm-node-version-management.md
├── server/
│   ├── data/                    # SQLite 数据目录（运行后生成）
│   ├── repositories/            # SQLite 读写层
│   ├── routers/                 # FastAPI 路由
│   ├── schemas/                 # Pydantic 模型
│   ├── services/                # Provider 代理与协议转换
│   ├── db.py                    # SQLite 初始化与连接
│   ├── main.py                  # FastAPI 应用入口
│   └── requirements.txt         # Python 依赖
├── src/
│   ├── apis/
│   │   ├── chat.ts              # 统一走本地后端 /api/chat/completions
│   │   ├── chats.ts             # SQLite 对话同步接口
│   │   ├── config.ts            # Provider 配置同步接口
│   │   ├── models.ts            # 通过本地后端获取模型列表
│   │   └── streaming.ts         # SSE / NDJSON 解析工具
│   ├── bridge/
│   │   └── moaBridge.ts         # Android WebView 桥接
│   ├── components/
│   │   ├── chat/
│   │   ├── settings/
│   │   └── sidebar/
│   ├── constants/
│   ├── pages/
│   ├── stores/
│   ├── types/
│   ├── utils/
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── android/
│   └── app/src/main/java/com/myopenweb/app/
│       ├── MainActivity.kt
│       ├── WebViewContainer.kt
│       ├── bridge/MoaBridge.kt
│       ├── native_/NativeSTT.kt
│       ├── native_/NativeTTS.kt
│       ├── native_/NativeFilePicker.kt
│       └── native_/SafeAreaHelper.kt
├── package.json
├── vite.config.ts               # /api 代理到 8000
└── .nvmrc
```

## 总体架构

```text
H5 Frontend (React)
  ├─ UI: Chat / Sidebar / Settings
  ├─ State: Zustand + localStorage cache
  ├─ Bridge: STT / TTS / File / SafeArea
  └─ API: /api/models /api/chat/completions /api/agent/completions /api/chats /api/config/provider
                │
                ▼
Local Backend (FastAPI)
  ├─ Config Router: Provider + embedding 配置读写
  ├─ Provider Verify: 连接自检与模型探测
  ├─ Models Router: 模型列表代理
  ├─ Chat Router: 聊天代理，统一输出 OpenAI SSE；可选 knowledge_id 触发 RAG 注入
  ├─ Agent Router: 工具调用循环（含 search_knowledge）
  ├─ Chats Router: SQLite 对话存取
  ├─ Files Router: 上传/列表/详情/删除，文本抽取后落盘
  ├─ Knowledge Router: 知识库 CRUD、绑定文件、建立索引、调试检索
  ├─ RAG Service: 切片 + 批量向量化 + 余弦 topK + 引用来源/拒答
  ├─ Embeddings Service: Ollama /api/embed 与 OpenAI /embeddings（含 WSL 回退）
  └─ Provider Service
       ├─ Ollama /v1 兼容接口
       ├─ Ollama /api/chat 原生图片接口
       └─ OpenAI Compatible 接口
                │
                ▼
SQLite (server/data/myopenweb.db)
  ├─ app_config           # 含 embedding_model
  ├─ chats
  ├─ agent_runs
  ├─ agent_steps
  ├─ memories
  ├─ files                # 文件元数据 + 抽取文本
  ├─ knowledge            # 知识库
  ├─ knowledge_file       # 知识库↔文件 多对多
  └─ chunks               # 切片 + embedding(JSON)

文件本体落盘到 server/data/files/
```

## 核心数据流

### 1. 聊天请求

```text
用户输入
→ MessageInput.onSend(text)
→ ChatPage.handleSend()
→ store.addMessage('user', text, files)
→ store.addMessage('assistant', '')
→ syncProviderConfig(settings)
→ POST /api/chat/completions
→ FastAPI 根据 provider 配置选择真实模型服务
   ├─ Ollama：统一转发原生 /api/chat，并转换成 OpenAI SSE / 标准 completion JSON
   └─ OpenAI Compatible：转发 /chat/completions
→ 前端统一用 createOpenAITextStream() 解析
→ appendContent(aiId, delta)
→ feedStreamTTS(delta)
→ 完成后 persistNow()
→ saveChat(activeConversation)
```

### 2. Provider 配置

```text
SettingsDrawer 修改 providerType / apiBaseUrl / apiKey
→ 保存到 localStorage
→ 用户点击“保存连接配置到后端”或模型刷新/聊天发送时触发 syncProviderConfig()
→ PUT /api/config/provider
→ SQLite.app_config 持久化
```

### 3. 对话同步

```text
App 启动
→ fetchProviderConfig()
→ fetchChats()
→ 本地 localStorage 与 SQLite 做按 updatedAt 合并
→ 以较新的版本为准回写到前端 Store
→ 本地较新的记录再回传 SQLite
```

## 模块说明

### 1. 前端 API 层 (`src/apis/`)

- `chat.ts`
  - 不再直连第三方模型服务，只请求本地后端 `/api/chat/completions`
  - 保留文件和图片消息的 OpenAI content-part 组装逻辑
- `config.ts`
  - `fetchProviderConfig()`：读取后端保存的 provider 配置
  - `syncProviderConfig()`：把当前设置同步给后端
- `chats.ts`
  - `fetchChats()` / `saveChat()` / `removeChat()`
  - 把本地对话缓存和 SQLite 连接起来
- `models.ts`
  - 统一请求 `/api/models`
  - 由后端代为访问真实 provider
- `streaming.ts`
  - `createOpenAITextStream()` 现在是主路径
  - `createOllamaTextStream()` 保留为兼容工具

### 2. 本地后端 (`server/`)

- `main.py`
  - 初始化 SQLite
  - 注册 CORS
  - 挂载全部路由
- `db.py`
  - 初始化 `app_config` 与 `chats` 两张表
  - 默认 provider 配置为 Ollama
- `routers/config.py`
  - `GET /api/config/provider`
  - `PUT /api/config/provider`
  - `POST /api/config/provider/verify`
    - 检测当前 provider 是否可连接
    - 返回配置地址、实际访问地址、模型数量、模型列表、错误信息
- `routers/models.py`
  - `GET /api/models`
- `routers/chat_proxy.py`
  - `POST /api/chat/completions`
  - 统一返回 OpenAI SSE，前端只维护一种流解析逻辑
- `routers/agent.py`
  - `POST /api/agent/completions`
  - Agent v1 入口，复用同一套聊天请求结构
  - 当前只开放后端白名单工具，不允许模型执行任意命令
  - `GET /api/agent/runs/{run_id}` 查询一次 Agent 运行详情
- `routers/memories.py`
  - `GET /api/memories`
  - `POST /api/memories`
  - `PUT /api/memories/{id}`
  - `DELETE /api/memories/{id}`
  - 管理手动长期记忆，Agent 请求时自动注入启用记忆
- `routers/chats.py`
  - `GET /api/chats`
  - `PUT /api/chats/{id}`
  - `DELETE /api/chats/{id}`
- `services/providers.py`
  - OpenAI Compatible 转发
  - Ollama 原生 `/api/chat` 转发
  - Ollama NDJSON → OpenAI SSE 协议转换
  - WSL 下自动尝试 `localhost` 和 Windows 主机网关地址，避免 Ollama 运行在 Windows 时本地后端连不上
- `services/agent_tools.py`
  - `get_current_time`：返回服务器当前时间
  - `calculator`：安全解析四则运算表达式，不使用 `eval`
  - `analyze_log`：正则抽取日志级别统计、错误行、异常类型，交模型归纳根因与排查建议
  - `summarize_git_diff`：解析 unified diff 的变更文件与增删行数，交模型生成变更摘要与风险点
  - `summarize_ticket`：抽取工单号/@相关人/链接/字段并给出摘要骨架
  - `generate_test_cases`：给出测试覆盖维度与关键参数，交模型生成结构化用例
  - `search_knowledge`：仅在选定知识库时开放，由 `agent_runner` 异步调用 `services/rag.py` 检索
- `services/file_extract.py`
  - txt/md 等文本直读，pdf 用 `pypdf`，docx 用 `python-docx`，缺依赖时报清晰错误而不崩溃
- `services/embeddings.py`
  - 批量向量化，复用 `providers.py` 的 URL 解析与 WSL 回退
- `services/rag.py`
  - 切片（按字符 + 自然边界 + overlap）、批量向量化后写入 `VectorStore`
  - 检索：向量 top-k + 关键词 top-k 由所选后端提供，本层做 RRF 融合 / rerank / 自纠错
  - 维度不匹配（换了 embedding 模型）时返回空并提示重建索引
  - 聊天融合：拼接带来源标注的参考资料 system_prompt，未命中时走拒答提示；检索链路异常时由 `chat_proxy` 降级为普通回答并带 `retrieval_warning`
- `vectorstores/`（向量存储抽象层）
  - `base.py`：`VectorStore` 协议（replace/count/delete + `query_by_vector` / `query_by_keywords` 两个排序原语）
  - `sqlite_store.py`：默认实现，JSON 向量 + numpy 内存余弦（带进程内矩阵缓存与版本戳失效）+ FTS5 BM25
  - `pgvector_store.py`：PostgreSQL + pgvector 实现，`ORDER BY embedding <=> q` 余弦 + tsvector 关键词检索
  - `factory.py`：按 `MYOPENWEB_VECTOR_BACKEND`（sqlite 默认 / pgvector）+ `MYOPENWEB_PG_DSN` 选择实现
- `services/agent_runner.py`
  - 要求模型输出 Open WebUI 风格的 `tool_calls` 数组
  - 兼容小模型把工具名直接写进 `action` 字段的情况
  - 根据模型决策调用白名单工具
  - 把工具结果回填给模型生成最终回答
  - 工具循环轮数可配置（`agent_max_rounds`，默认 3，clamp 1-10），避免无限调用
  - 知识库检索失败时工具返回结构化错误（模型转告用户），运行不中断
  - 写入 `agent_runs` / `agent_steps`，记录模型判断、工具调用、工具结果、最终回答
  - 注入已启用 `memories` 作为长期上下文

### 3. 状态管理 (`src/stores/`)

使用单一 `useAppStore` 管理：

- `conversations`
- `activeConversationId`
- `generating`
- `settings`
- `pendingFiles`
- `sidebarOpen`
- `settingsOpen`

持久化策略：

- 设置先写 `localStorage`
- Provider 配置再同步到 SQLite
- 对话先写 `localStorage`
- 流结束后同步到 SQLite
- 文件内容在本地持久化时仍然剥离，避免 localStorage 膨胀

### 4. 设置面板 (`src/components/settings/SettingsDrawer.tsx`)

当前设置分成两类：

- Provider 连接配置
  - `providerType`
  - `apiBaseUrl`
  - `apiKey`
  - 可手动保存到后端
  - 可点击“测试连接”检查 provider 是否可访问
- Agent 配置
  - `agentEnabled`
  - 开启后聊天请求走 `/api/agent/completions`
  - 关闭后保持普通聊天代理路径
- 聊天运行参数
  - `model`
  - `systemPrompt`
  - `temperature`
  - `maxTokens`
  - `streamOutput`
  - `ttsEnabled / ttsLang / ttsRate`

### 5. 对话与侧边栏 (`src/components/sidebar/Sidebar.tsx`)

- 支持新建、切换、删除
- 按标题和内容搜索
- Markdown / JSON 导出
- 删除时会同时删除 SQLite 中的记录

### 6. 文件与图片消息

- 浏览器环境：`<input type="file">`
- Android WebView：优先走原生 `pickFile()`
- 文本文件：
  - 作为上下文拼接进消息文本
- 图片文件：
  - 作为 OpenAI content-part 的 `image_url`
  - 对于 Ollama，后端统一走原生 `/api/chat`

### 7. TTS / STT

- TTS：仍使用浏览器 `speechSynthesis`
- STT：
  - 浏览器优先尝试 `SpeechRecognition`
  - Android WebView 回退到原生 `NativeSTT`

### 8. Android Bridge

桥接接口：

- `startSTT()` / `stopSTT()`
- `playTTS()` / `stopTTS()`
- `pickFile()`
- `goBack()`
- `setTitle()`
- `getSafeArea()`

本轮修正：

- H5 端统一通过 `JSON.stringify(params)` 调 `callNative()`
- Android 权限回调已回接到 `NativeSTT.onPermissionResult()`
- WebView 容器暴露 `getBridge()` 供 Activity 权限回调使用

## 数据库设计

### `app_config`

| 字段 | 说明 |
|------|------|
| `key` | 配置键 |
| `value` | 配置值 |
| `updated_at` | 更新时间 |

当前使用的键：

- `provider_type`
- `provider_base_url`
- `provider_api_key`
- `embedding_model`（知识库向量化模型，默认 `bge-m3`）

### `chats`

| 字段 | 说明 |
|------|------|
| `id` | 对话 ID |
| `title` | 对话标题 |
| `payload` | 完整对话 JSON |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

设计原则：

- 当前阶段优先简单可靠，不拆 message/file 多表
- 先把“能稳定同步和恢复”做好
- 后续若要做检索、附件复用、消息级索引，再拆分表结构

### `agent_runs`

| 字段 | 说明 |
|------|------|
| `id` | Agent 运行 ID |
| `conversation_id` | 关联对话 ID |
| `message_id` | 关联 assistant 消息 ID |
| `user_message_id` | 关联 user 消息 ID |
| `model` | 使用的模型 |
| `user_input` | 用户输入 |
| `final_answer` | 最终回答 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

### `agent_steps`

| 字段 | 说明 |
|------|------|
| `id` | 步骤 ID |
| `run_id` | 关联 Agent 运行 ID |
| `step_index` | 步骤序号 |
| `type` | `model_decision` / `tool_call` / `tool_result` / `final` |
| `name` | 工具名或步骤名 |
| `input_json` | 输入 JSON |
| `output_json` | 输出 JSON |
| `ok` | 是否成功 |
| `error` | 错误信息 |
| `created_at` | 创建时间 |

### `memories`

| 字段 | 说明 |
|------|------|
| `id` | Memory ID |
| `content` | 记忆内容 |
| `category` | `preference` / `profile` / `project` / `fact` |
| `enabled` | 是否注入 Agent |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

### `files`

| 字段 | 说明 |
|------|------|
| `id` | 文件 ID |
| `filename` | 原始文件名 |
| `path` | 落盘路径（server/data/files/） |
| `mime_type` | MIME 类型 |
| `size` | 字节大小 |
| `hash` | 内容 SHA-256 |
| `text_content` | 抽取出的纯文本 |
| `meta_json` | 预留元数据 |
| `created_at` / `updated_at` | 时间戳 |

### `knowledge`

| 字段 | 说明 |
|------|------|
| `id` | 知识库 ID |
| `name` | 知识库名称 |
| `description` | 描述 |
| `created_at` / `updated_at` | 时间戳 |

### `knowledge_file`

| 字段 | 说明 |
|------|------|
| `knowledge_id` | 知识库 ID |
| `file_id` | 文件 ID |
| `created_at` | 绑定时间 |

知识库与文件多对多，主键 `(knowledge_id, file_id)`。

### `chunks`

| 字段 | 说明 |
|------|------|
| `id` | 分块 ID |
| `knowledge_id` | 所属知识库 |
| `file_id` | 来源文件 |
| `chunk_index` | 分块序号 |
| `content` | 分块文本 |
| `embedding` | 向量（JSON 数组字符串） |
| `created_at` | 创建时间 |

设计原则：chunks 归属 `VectorStore` 抽象层管理。默认 SQLite 后端把向量以 JSON 存进本表、查询用 numpy 内存余弦（进程内矩阵缓存 + 版本戳失效）；设置 `MYOPENWEB_VECTOR_BACKEND=pgvector` 后 chunks 改存 PostgreSQL（`vector` 列 + tsvector 关键词索引），业务表（chats/files/knowledge 等）仍留在 SQLite，切换后需重建索引。

## 默认配置

| 配置项 | 默认值 |
|--------|--------|
| Provider | `ollama` |
| API 地址 | `http://localhost:11434/v1` |
| API Key | 空 |
| Agent 模式 | `false` |
| Agent 最大工具轮数 | `3`（设置页可调 1-10） |
| 向量后端 | `sqlite`（环境变量 `MYOPENWEB_VECTOR_BACKEND` 可切 `pgvector`） |
| 模型 | `qwen3.5:4b` |
| System Prompt | `You are a helpful assistant.` |
| 温度 | `0.7` |
| Max Tokens | `4096` |
| 流式输出 | `true` |
| TTS 自动朗读 | `false` |
| TTS 语言 | `zh-CN` |
| TTS 速度 | `1.0` |

## 开发命令

```bash
# 首次初始化本地后端
python3 -m venv .venv
./.venv/bin/pip install -r server/requirements.txt

# 前端
pnpm dev
pnpm build
pnpm preview

# 后端
pnpm dev:server
pnpm server

# Windows PowerShell 一键启动后端（推荐给 Windows + WSL 环境）
.\scripts\dev-server.ps1

# Windows 双击/命令行启动后端
.\start-backend.bat
```

### 本地开发建议

1. 先启动后端：Windows 推荐双击 `start-backend.bat`；PowerShell 可用 `.\scripts\dev-server.ps1`；WSL 内可用 `pnpm dev:server`
2. 再启动前端：`pnpm dev`
3. 前端通过 Vite 代理把 `/api/*` 转到后端；Windows + WSL 环境会自动使用 WSL IP，其他环境默认 `http://127.0.0.1:8000`

## 已完成功能

- [x] React + TypeScript + Vite + Tailwind 聊天前端
- [x] Markdown / 代码高亮 / 文件与图片消息
- [x] 多轮对话与侧边栏管理
- [x] TTS 流式朗读
- [x] Android WebView 壳工程
- [x] Android 原生 STT / TTS / 文件选择 / 安全区桥接
- [x] FastAPI 本地后端骨架
- [x] SQLite 配置与聊天持久化
- [x] Provider 配置同步到本地后端
- [x] Provider 连接自检与设置页测试按钮
- [x] 模型列表统一由后端代理
- [x] 聊天统一走本地后端
- [x] Agent v1 最小工具调用循环
- [x] Agent v1 安全工具：当前时间、计算器
- [x] Agent 研发/运维工具：日志分析、Git diff 摘要、工单总结、测试用例生成
- [x] Agent 运行日志 v1：记录模型判断、工具调用、工具结果、最终回答
- [x] Agent 工具调用格式改为 Open WebUI 风格的 `tool_calls` 数组
- [x] Agent 日志详情前端展开面板
- [x] Memory 简化版：手动新增、启用/停用、删除，并注入 Agent
- [x] 文件落盘 + 文本抽取（txt/md/pdf/docx），独立 `files` 表
- [x] 自研 RAG 知识库：建库、传文件、切片、向量化、余弦 topK 检索
- [x] 聊天选知识库：命中片段注入 system_prompt，带引用来源，库外问题拒答
- [x] RAG × Agent 融合：`search_knowledge` 工具 + 运行日志记录 + 引用来源
- [x] 设置页可配置 embedding 模型，前端知识库管理抽屉 + 引用来源展示
- [x] 混合检索：SQLite FTS5 BM25 + 向量余弦经 RRF 融合，自研 CJK 二元组分词，设置页可切换
- [x] Rerank：bge-reranker cross-encoder 可开关重排，依赖缺失自动回退（`server/rerank/`）
- [x] 检索质量评测：40 条 QA 评测集 + Hit@K/MRR/延迟参数对照报告（`server/eval/`）
- [x] 后端单元测试（切片/分词/Agent JSON 解析/混合检索）+ GitHub Actions CI
- [x] Docker 多阶段构建 + docker-compose（可选 Ollama profile），FastAPI 托管 H5
- [x] Ollama 图片请求自动切到原生 `/api/chat`
- [x] Ollama NDJSON 在后端转换为 OpenAI SSE
- [x] localStorage 与 SQLite 的启动合并同步
- [x] WebView bridge JSON 参数修正
- [x] Android STT 权限回调接通

## Android 壳工程

位于 `android/` 子目录，Kotlin + Gradle 独立构建。

### 技术栈

- 语言：Kotlin
- 最低 API：26（Android 8.0）
- Target API：34（Android 14）
- 构建：Gradle 8.5 + AGP 8.2.2
- 纯原生 API，无第三方业务依赖

### H5 加载策略

- **DEBUG**：加载开发服务器
- **RELEASE**：加载 `file:///android_asset/web/index.html`
- 通过 `BuildConfig.DEBUG` 自动切换

### Bridge 通信流程

```text
H5: window.moaBridge.callNative(method, JSON.stringify(params))
→ Android: MoaBridge.callNative(method, paramsJson)
→ NativeSTT / NativeTTS / NativeFilePicker / SafeAreaHelper
→ evaluateJavascript("window[cbFuncName](data)")
→ H5 Promise resolve
```

## 当前边界

当前版本已经具备：

- 单用户本地使用
- 本地配置管理
- 对话持久化
- 移动端壳接入
- Ollama / OpenAI Compatible 模型代理
- WSL → Windows Ollama 自动回退访问

当前还没有做：

- 用户系统
- 权限控制
- 工作流 / Dify 式可视化编排
- Redis / 多设备同步
- 文件级增量索引（当前为知识库整体重建）

## 后续迭代方向

- [x] 文件内容入库或落盘，支持历史附件真正可重放
- [x] 简单知识库：文件列表、文本抽取、按关键词/向量注入上下文
- [x] RAG / 向量检索接入
- [x] 检索增强：rerank、混合检索（BM25 + 向量 RRF）
- [x] PostgreSQL + pgvector 可切换向量后端（`server/vectorstores/` 抽象层，环境变量切换，双后端契约测试）
- [ ] 按文件增量索引（当前为知识库整体重建）
- [ ] 聊天消息与附件拆表，替代当前单 JSON 存储
- [ ] 模型配置中心扩展为多 provider 列表
- [ ] 统一错误码与后端日志
- [ ] 更好的 TTS（Edge TTS / OpenAI TTS）
- [ ] 主题切换与更完整的移动端交互优化

## 下一步执行计划（入门路线）

当前推荐不要直接上 Dify 式工作流，也不要马上引入复杂数据库。  
下一阶段目标是：让本地开发链路更可观测，然后用最小闭环理解 Agent 的核心结构。

### 第 1 步：稳定启动与连接自检（已完成）

目标：用户能明确知道是哪一层出问题，而不是只看到前端 `HTTP 500`。

已完成：

- 后端新增 `POST /api/config/provider/verify`
- 返回当前 provider 类型、配置地址、实际访问地址、模型数量、错误信息
- 设置页新增“测试连接”按钮
- 测试成功后显示可用模型列表摘要
- 测试失败时显示明确原因，例如 FastAPI 未启动、Ollama 未启动、模型服务不可达、API Key 错误

学习点：

- FastAPI 路由如何组织
- Pydantic 返回结构如何设计
- 前端如何调用后端接口
- UI 如何处理 loading / success / error 状态

### 第 2 步：Agent v1，最小工具调用循环（已完成）

目标：从“普通聊天 App”进入“Agent App”。

已完成两个安全工具：

- `get_current_time`：获取当前时间
- `calculator`：执行简单四则运算

一次 Agent 请求的基本流程：

```text
用户输入
→ 后端构造 system prompt，告诉模型有哪些工具
→ 模型判断是否需要调用工具
→ 后端执行工具
→ 把工具结果再交给模型
→ 模型生成最终回答
→ 前端展示
```

学习点：

- Agent 不是神秘能力，本质是“模型 + 工具 + 控制循环”
- 工具必须由后端白名单控制，不能让模型直接执行任意命令
- 每次工具调用都应该记录日志，方便调试

当前实现边界：

- Agent v1 依赖模型按 JSON 协议输出，模型不稳定时可能需要重试或改进提示词
- 已兼容 `{"action":"calculator","expression":"..."}` 这类小模型常见错误格式
- 当前主协议已调整为 `{"tool_calls":[{"name":"calculator","parameters":{...}}]}`
- 当前流式响应是“最终答案一次性 SSE 输出”，不是逐 token 展示 Agent 中间过程

### 第 3 步：Agent 运行日志（已完成 v1）

目标：让你能看懂 Agent 为什么这么回答。

已记录：

- 用户输入
- 模型第一次判断
- 调用的工具名
- 工具参数
- 工具返回结果
- 最终回答

当前前端展示：

- assistant 消息下显示 `Agent 调用 N 个工具：tool_name`
- 详细步骤可通过 `GET /api/agent/runs/{run_id}` 查询

学习点：

- 可观测性比“功能多”更重要
- Agent 出错时，日志能快速定位是模型判断错、工具参数错，还是工具执行错

### 第 4 步：记忆与偏好（已完成简化版）

目标：让 App 开始像“个人助手”，而不只是一次性聊天。

已完成简单记忆：

- 用户昵称
- 常用语言
- 常用技术栈
- 默认回答风格
- 项目路径和项目目标摘要

当前实现：

- 设置页可新增 memory
- 支持 `fact` / `preference` / `profile` / `project` 分类
- 支持启用、停用、删除
- Agent 请求自动注入已启用 memory
- 暂不做 embedding，相似度检索留到 RAG 阶段

学习点：

- 记忆不是把所有聊天塞进 prompt
- 应该把稳定偏好和长期事实单独存储
- 每次请求只注入必要记忆

### 第 5 步：文件知识库 / RAG

目标：让 Agent 能回答项目文档、代码片段、个人资料里的问题。

建议等前 4 步稳定后再做：

- 文件落盘
- 文本切分
- 向量索引
- 相似度检索
- 检索结果注入 prompt

学习点：

- RAG 是“检索 + 上下文注入”，不是简单上传文件
- 文件、分块、索引、引用来源要分开设计

## 参考来源

本项目骨架参考 Open WebUI（v0.8.12）以下方向：

- 聊天页结构
- 模型代理与配置分层
- 流式输出处理
- 音频能力接入思路
- 聊天持久化建模方式

更具体的 Open WebUI 对照拆解见：

- `docs/open-webui-analysis.md`
