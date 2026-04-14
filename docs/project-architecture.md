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
| Markdown | react-markdown | 9.x |
| SSE 解析 | eventsource-parser | 1.x |
| Node | Node.js | 18.18.0（见 .nvmrc） |

## 目录结构

```
MyOpenWeb/
├── docs/                        # 项目文档
│   └── project-architecture.md  # 本文件
├── src/
│   ├── apis/                    # API 接口层
│   │   ├── chat.ts              # chatCompletion() - 对接 Ollama/OpenAI 兼容 API
│   │   └── streaming.ts         # createOpenAITextStream() - SSE 流式解析
│   ├── bridge/                  # Android WebView 桥接
│   │   └── moaBridge.ts         # moaBridge 接口（STT/TTS/文件/导航/安全区域）
│   ├── components/
│   │   └── chat/                # 聊天组件集
│   │       ├── ChatNavbar.tsx   # 顶栏：App名称 + 模型名 + 新对话按钮
│   │       ├── ChatPlaceholder.tsx  # 空状态占位页
│   │       ├── FileButton.tsx   # 文件附件按钮（预留）
│   │       ├── MessageBubble.tsx    # 消息气泡（用户/AI，AI 支持 Markdown）
│   │       ├── MessageInput.tsx # 输入区：文本框 + 语音 + 文件 + 发送/停止
│   │       ├── MessageList.tsx  # 消息列表（自动滚动）
│   │       └── VoiceButton.tsx  # 语音输入（Web Speech API + moaBridge 预留）
│   ├── constants/
│   │   └── index.ts             # 默认 API 地址、模型名等配置
│   ├── pages/
│   │   └── ChatPage.tsx         # 聊天页主入口，串联所有组件 + 流式交互
│   ├── stores/
│   │   └── index.ts             # Zustand 状态管理（消息、设置、生成状态）
│   ├── types/
│   │   ├── index.ts             # 核心类型（ChatMessage, AppSettings 等）
│   │   └── speech.d.ts          # Web Speech API 类型声明
│   ├── App.tsx                  # 应用根组件
│   ├── main.tsx                 # 入口
│   ├── index.css                # Tailwind + 全局样式 + 安全区域变量
│   └── vite-env.d.ts            # Vite 类型引用
├── .gitignore
├── .nvmrc                       # Node 版本锁定 (18.18.0)
├── index.html                   # HTML 入口（viewport 手机适配）
├── package.json
├── postcss.config.js
├── tailwind.config.js
├── tsconfig.json
├── tsconfig.node.json
└── vite.config.ts               # Vite 配置（@ 路径别名）
```

## 核心数据流

```
用户输入 → MessageInput.onSend(text)
         → ChatPage.handleSend()
           → useChatStore.addMessage('user', text)
           → useChatStore.addMessage('assistant', '')
           → chatCompletion({ baseUrl, model, messages, stream: true })
             → fetch POST /chat/completions
           → createOpenAITextStream(response.body)
             → SSE EventSourceParser 逐 token 解析
           → for await (update of stream)
             → useChatStore.appendContent(aiId, update.value)
             → MessageList 自动滚动
         → 完成后 updateMessage(aiId, { done: true })
```

## 模块说明

### 1. API 层 (src/apis/)

- **chat.ts** - `chatCompletion()` 函数，发送 OpenAI 兼容格式的请求，返回 `[Response, AbortController]`。支持 stream/非 stream 两种模式。可对接 Ollama（默认 `localhost:11434/v1`）和任何 OpenAI 兼容 API。
- **streaming.ts** - `createOpenAITextStream()` 函数，将 SSE 响应流转为 async generator。移植自 Open WebUI 的 `src/lib/apis/streaming/index.ts`，核心链路：`ReadableStream → TextDecoderStream → EventSourceParserStream → yield { value, done }`。

### 2. 状态管理 (src/stores/)

使用 Zustand，单一 store 包含：
- `messages: ChatMessage[]` - 当前对话消息列表
- `generating: boolean` - 是否正在生成
- `settings: AppSettings` - 用户设置（API 地址、模型、温度等），自动持久化到 localStorage

### 3. 聊天组件 (src/components/chat/)

三层布局：
- **ChatNavbar** - 固定顶栏，显示 App 名称和当前模型
- **MessageList** - 可滚动消息区，智能自动滚动（用户手动上滑时暂停）
- **MessageInput** - 固定底栏，包含文本输入、语音按钮、文件按钮、发送/停止按钮

消息渲染：
- 用户消息 → 右对齐蓝色气泡
- AI 消息 → 左对齐，通过 react-markdown 渲染 Markdown（代码块、行内代码等）
- 错误消息 → 红色提示框

### 4. Android 桥接 (src/bridge/)

遵循项目已有的 moaBridge 模式，预定义接口：
- **STT**: `startSTT()` / `stopSTT()` - 语音识别
- **TTS**: `playTTS()` / `stopTTS()` - 语音合成
- **文件**: `pickFile()` - 文件选择
- **导航**: `goBack()` / `setTitle()` - 页面导航
- **安全区域**: `getSafeArea()` - 获取状态栏/底部栏高度

所有带回调的接口统一使用 `cbFuncName + window[cbFuncName]` 模式，与 Android 原生通过 `callNative` 通信。

### 5. 移动端适配

- `index.html` viewport: `width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover`
- CSS 变量 `--safe-area-top` / `--safe-area-bottom` 适配刘海屏
- 全局禁用 user-select（输入框除外），禁用 tap-highlight
- 不使用响应式布局，全部按手机尺寸设计

## 默认配置

| 配置项 | 默认值 |
|--------|--------|
| API 地址 | `http://localhost:11434/v1` (Ollama) |
| 模型 | `qwen2.5:7b` |
| System Prompt | `You are a helpful assistant.` |
| 温度 | 0.7 |
| Max Tokens | 4096 |
| 流式输出 | 开启 |

## 开发命令

```bash
npm run dev      # 启动开发服务器 (http://localhost:5173)
npm run build    # TypeScript 检查 + 生产构建
npm run preview  # 预览生产构建
```

## Node 版本管理

项目根目录有 `.nvmrc` 文件锁定 Node 18.18.0。

推荐使用 fnm 自动切换版本：
```bash
# 安装 fnm（Windows）
winget install Schniz.fnm

# PowerShell Profile 加入自动切换
# 编辑 $PROFILE 文件，加入：
fnm env --use-on-cd --shell powershell | Out-String | Invoke-Expression

# 之后 cd 到项目目录会自动切换 Node 版本
```

也可继续用 nvm-windows 手动切换：
```bash
nvm install 18.18.0
nvm use 18.18.0
```

## 参考来源

本项目骨架参考 Open WebUI (v0.8.12) 的以下模块：
- 聊天页结构: `src/lib/components/chat/Chat.svelte`
- 流式输出: `src/lib/apis/streaming/index.ts`
- 模型接入: `src/lib/apis/openai/index.ts`
- 语音接口: `src/lib/apis/audio/index.ts` + `src/lib/utils/audio.ts`
- 状态管理: `src/lib/stores/index.ts`

## 后续迭代方向

- [ ] 对话历史持久化（IndexedDB / localStorage）
- [ ] 多轮对话管理（对话列表 + 侧边栏）
- [ ] 设置页面（API 地址、模型选择、温度等可视化配置）
- [ ] 文件上传 + 传入 context
- [ ] RAG 向量检索接入
- [ ] TTS 流式播放（AudioQueue 队列机制）
- [ ] Android WebView 壳工程
- [ ] 原生桥接实际对接（STT/TTS/文件选择）
