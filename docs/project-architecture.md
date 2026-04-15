# MyOpenWeb 项目架构文档

## 项目定位

基于 Open WebUI 拆解的个人版 AI App 骨架。  
H5 聊天页 + Android WebView 壳 + 原生桥接 + 语音输入输出 + Ollama/OpenAI API 接入。

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 构建 | Vite | 5.x |
| 框架 | React | 18.x |
| 语言 | TypeScript | 5.x |
| 样式 | Tailwind CSS | 3.x |
| 状态管理 | Zustand | 4.x |
| Markdown | react-markdown + remark-gfm | 9.x |
| 代码高亮 | react-syntax-highlighter (hljs Light) | 16.x |
| SSE 解析 | eventsource-parser | 1.x |
| 包管理 | pnpm | 10.x |
| Node | Node.js | 18.18.0（见 .nvmrc） |

## 目录结构

```
MyOpenWeb/
├── docs/                              # 项目文档
│   ├── project-architecture.md        # 本文件
│   └── fnm-node-version-management.md # fnm 版本管理指南
├── src/
│   ├── apis/                          # API 接口层
│   │   ├── chat.ts                    # chatCompletion() - 对接 Ollama/OpenAI 兼容 API
│   │   ├── models.ts                  # fetchModels() - 自动获取模型列表
│   │   └── streaming.ts              # createOpenAITextStream() - SSE 流式解析
│   ├── bridge/                        # Android WebView 桥接
│   │   └── moaBridge.ts              # moaBridge 接口（STT/TTS/文件/导航/安全区域）
│   ├── components/
│   │   ├── chat/                      # 聊天组件集
│   │   │   ├── ChatNavbar.tsx         # 顶栏：侧边栏入口 + App名称 + 模型名 + 新对话 + 设置
│   │   │   ├── ChatPlaceholder.tsx    # 空状态占位页
│   │   │   ├── CodeBlock.tsx          # 代码块：语法高亮 + 复制按钮
│   │   │   ├── FileButton.tsx         # 文件附件按钮（读取文本文件内容）
│   │   │   ├── FilePreviews.tsx       # 文件预览条（输入框上方）
│   │   │   ├── MessageBubble.tsx      # 消息气泡（用户/AI，AI 支持 Markdown + 代码高亮 + GFM 表格）
│   │   │   ├── MessageInput.tsx       # 输入区：文本框 + 语音 + 文件 + 发送/停止
│   │   │   ├── MessageList.tsx        # 消息列表（自动滚动）
│   │   │   └── VoiceButton.tsx        # 语音输入（Web Speech API + moaBridge 预留）
│   │   ├── settings/
│   │   │   └── SettingsDrawer.tsx     # 设置抽屉（右侧滑入）
│   │   └── sidebar/
│   │       └── Sidebar.tsx            # 对话列表侧边栏（左侧滑入）
│   ├── constants/
│   │   └── index.ts                   # 默认配置、存储 Key、文件限制
│   ├── pages/
│   │   └── ChatPage.tsx               # 聊天页主入口，串联所有组件 + 流式交互 + TTS
│   ├── stores/
│   │   └── index.ts                   # Zustand 状态管理（多对话 + 设置 + 持久化）
│   ├── types/
│   │   ├── index.ts                   # 核心类型（ChatMessage, Conversation, AppSettings 等）
│   │   └── speech.d.ts                # Web Speech API 类型声明
│   ├── utils/
│   │   └── tts.ts                     # TTS 工具（流式分句朗读 speechSynthesis）
│   ├── App.tsx                        # 应用根组件（挂载 Sidebar + SettingsDrawer）
│   ├── main.tsx                       # 入口
│   ├── index.css                      # Tailwind + 全局样式 + 安全区域 + 滑入动画
│   └── vite-env.d.ts                  # Vite 类型引用
├── .gitignore
├── .nvmrc                             # Node 版本锁定 (18.18.0)
├── index.html                         # HTML 入口（viewport 手机适配）
├── package.json
├── pnpm-lock.yaml
├── postcss.config.js
├── tailwind.config.js                 # Tailwind 配置（自定义 neutral-750 + primary 色板）
├── tsconfig.json
├── tsconfig.node.json
└── vite.config.ts                     # Vite 配置（@ 路径别名）
```

## 核心数据流

```
用户输入 → MessageInput.onSend(text)
         → ChatPage.handleSend()
           → useAppStore.addMessage('user', text, files?)
           → useAppStore.addMessage('assistant', '')
           → chatCompletion({ baseUrl, apiKey, model, messages, files, stream: true })
             → fetch POST /chat/completions
           → createOpenAITextStream(response.body)
             → SSE EventSourceParser 逐 token 解析
           → for await (update of stream)
             → useAppStore.appendContent(aiId, update.value)  [不触发持久化]
             → feedStreamTTS(update.value)  [TTS 流式朗读]
             → MessageList 自动滚动
         → 完成后 updateMessage(aiId, { done: true })
         → persistNow()  [统一写入 localStorage]
         → flushStreamTTS()  [朗读剩余文本]
```

## 模块说明

### 1. API 层 (src/apis/)

- **chat.ts** - `chatCompletion()` 函数，发送 OpenAI 兼容格式的请求，返回 `[Response, AbortController]`。支持 stream/非 stream 两种模式，支持 API Key，支持文件 context 注入。可对接 Ollama（默认 `localhost:11434/v1`）和任何 OpenAI 兼容 API。
- **streaming.ts** - `createOpenAITextStream()` 函数，将 SSE 响应流转为 async generator。移植自 Open WebUI 的 `src/lib/apis/streaming/index.ts`，核心链路：`ReadableStream → TextDecoderStream → EventSourceParserStream → yield { value, done }`。
- **models.ts** - `fetchModels()` 函数，调用 `GET /v1/models` 获取已安装的模型列表。兼容 Ollama 和 OpenAI 格式响应，5s 超时。

### 2. 状态管理 (src/stores/)

使用 Zustand，单一 `useAppStore` 包含：
- `conversations: Conversation[]` - 所有对话列表
- `activeConversationId: string | null` - 当前激活对话
- `generating: boolean` - 是否正在生成
- `settings: AppSettings` - 用户设置（API 地址、API Key、模型、温度、TTS 等）
- `pendingFiles: FileAttachment[]` - 待发送文件附件
- `sidebarOpen / settingsOpen` - UI 抽屉状态

**持久化策略**：
- 设置 → `localStorage['mow-settings']`，变更时立即写入
- 对话列表 → `localStorage['mow-conversations']`，发送用户消息时写入，流式输出期间不写入（避免每 token 写一次），流式完成后通过 `persistNow()` 统一写入
- 文件内容 → 持久化时剥离（只保留文件名/大小/类型），避免 localStorage 爆满
- 当前对话 ID → `localStorage['mow-active-id']`

### 3. 聊天组件 (src/components/chat/)

三层布局：
- **ChatNavbar** - 固定顶栏：左侧汉堡图标打开侧边栏，显示 App 名称和当前模型，右侧新对话按钮 + 设置齿轮图标
- **MessageList** - 可滚动消息区，智能自动滚动（用户手动上滑时暂停）
- **MessageInput** - 固定底栏，包含文本输入、语音按钮、文件按钮、发送/停止按钮。上方显示文件预览条（FilePreviews）

消息渲染：
- 用户消息 → 右对齐蓝色气泡，附件显示为文件标签
- AI 消息 → 左对齐，通过 react-markdown 渲染：
  - 代码块 → CodeBlock 组件（react-syntax-highlighter 语法高亮 + 语言标签 + 复制按钮）
  - 表格 → remark-gfm 解析 + 自定义样式（带边框、表头高亮）
  - 行内代码 → 灰底圆角样式
- 错误消息 → 红色提示框

支持高亮的语言：JavaScript/TypeScript/JSX/TSX、Python、Java、JSON、Bash/Shell、SQL、CSS、HTML/XML、Markdown、Go、Rust、C/C++、YAML

### 4. 设置面板 (src/components/settings/)

- **SettingsDrawer** - 右侧滑入抽屉，配置项：
  - API 地址、API Key
  - 模型选择：打开时自动调用 `fetchModels()` 获取模型列表，下拉选择；如获取失败则回退为手动输入；支持刷新按钮
  - 系统提示词（文本区域）
  - 温度、最大 Tokens（滑块）
  - 流式输出开关
  - TTS 自动朗读开关、朗读语言、朗读速度

### 5. 多对话管理 (src/components/sidebar/)

- **Sidebar** - 左侧滑入侧边栏：
  - 新建对话按钮
  - 对话列表（按创建时间倒序），点击切换
  - hover 显示删除按钮
  - 对话标题自动取首条用户消息前 30 字
  - 底部设置入口

### 6. 文件上传 (FileButton + FilePreviews)

- 支持 .txt/.md/.json/.csv/.py/.js/.ts 等常见文本格式，限制 5MB
- 选择后在输入框上方显示文件预览条，可单独移除
- 发送时文件内容以 `--- File: xxx ---\ncontent\n--- End ---` 格式拼接到消息中

### 7. TTS 流式播放 (src/utils/tts.ts)

- 基于 `speechSynthesis` API
- 流式分句朗读：按句子边界（。！？.!?\n）切分，一句完整后立即提交朗读
- 设置里可配置：语言（中/英/日）、速度（0.5x-2.0x）
- 停止生成时同时停止朗读

### 8. Android 桥接 (src/bridge/)

遵循项目已有的 moaBridge 模式，预定义接口：
- **STT**: `startSTT()` / `stopSTT()` - 语音识别
- **TTS**: `playTTS()` / `stopTTS()` - 语音合成
- **文件**: `pickFile()` - 文件选择
- **导航**: `goBack()` / `setTitle()` - 页面导航
- **安全区域**: `getSafeArea()` - 获取状态栏/底部栏高度

所有带回调的接口统一使用 `cbFuncName + window[cbFuncName]` 模式，与 Android 原生通过 `callNative` 通信。

### 9. 移动端适配

- `index.html` viewport: `width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover`
- CSS 变量 `--safe-area-top` / `--safe-area-bottom` 适配刘海屏
- 按钮/导航禁用 user-select，聊天区域允许选中复制
- 不使用响应式布局，全部按手机尺寸设计

## 默认配置

| 配置项 | 默认值 |
|--------|--------|
| API 地址 | `http://localhost:11434/v1` (Ollama) |
| API Key | 空（Ollama 不需要） |
| 模型 | `qwen2.5:3b` |
| System Prompt | `You are a helpful assistant.` |
| 温度 | 0.7 |
| Max Tokens | 4096 |
| 流式输出 | 开启 |
| TTS 自动朗读 | 关闭 |
| TTS 语言 | zh-CN |
| TTS 速度 | 1.0x |

## 开发命令

```bash
pnpm dev        # 启动开发服务器 (http://localhost:5173)
pnpm build      # TypeScript 检查 + 生产构建
pnpm preview    # 预览生产构建
pnpm tsc        # 仅 TypeScript 类型检查
```

## Node 版本管理

项目根目录有 `.nvmrc` 文件锁定 Node 18.18.0。

推荐使用 fnm 自动切换版本（详见 `docs/fnm-node-version-management.md`）：
```bash
# 安装 fnm（Windows）
winget install Schniz.fnm

# PowerShell Profile 加入自动切换
# 编辑 $PROFILE 文件，加入：
fnm env --use-on-cd --shell powershell | Out-String | Invoke-Expression
```

## 参考来源

本项目骨架参考 Open WebUI (v0.8.12) 的以下模块：
- 聊天页结构: `src/lib/components/chat/Chat.svelte`
- 流式输出: `src/lib/apis/streaming/index.ts`
- 模型接入: `src/lib/apis/openai/index.ts`
- 语音接口: `src/lib/apis/audio/index.ts` + `src/lib/utils/audio.ts`
- 状态管理: `src/lib/stores/index.ts`

## 已完成功能

- [x] 项目初始化：React + TypeScript + Vite + Tailwind + pnpm
- [x] 聊天页骨架：ChatNavbar + MessageList + MessageInput 三层布局
- [x] 流式输出：SSE 解析，对接 Ollama OpenAI 兼容端点
- [x] 模型接入层：chatCompletion API，支持 base URL / model / apiKey
- [x] 设置页面：侧滑抽屉，可视化配置所有参数
- [x] 模型列表自动获取：从 API 拉取已安装模型，下拉选择
- [x] 对话历史持久化：localStorage，刷新页面不丢失
- [x] 多轮对话管理：侧边栏对话列表，新建/切换/删除
- [x] 文件上传：读取文本文件内容作为 context 发给模型
- [x] TTS 流式播放：AI 回复自动分句朗读
- [x] 语音输入：Web Speech API STT + moaBridge 预留
- [x] Markdown 渲染增强：代码语法高亮 + 复制按钮 + GFM 表格
- [x] Android Bridge 接口预定义

## 后续迭代方向

- [ ] 对话导出/分享（Markdown / JSON）
- [ ] RAG 向量检索接入
- [ ] Android WebView 壳工程
- [ ] 原生桥接实际对接（STT/TTS/文件选择）
- [ ] 图片消息支持（多模态模型）
- [ ] 对话搜索
- [ ] 主题切换（亮色/暗色）
