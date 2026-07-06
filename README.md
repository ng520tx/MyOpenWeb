# MyOpenWeb — 企业研发/运维 AI Copilot 工作台

[![CI](https://github.com/ng520tx/MyOpenWeb/actions/workflows/ci.yml/badge.svg)](https://github.com/ng520tx/MyOpenWeb/actions/workflows/ci.yml)

面向研发、运维、交付团队的移动端 AI 助手：**Android 原生壳 + React H5 流式聊天 + FastAPI 分层后端 + 自研 RAG 知识库 + 工具型 Agent**，全本地运行、零外部服务依赖，可企业内网私有化部署。

> RAG 与 Agent 全部自研（不依赖 LangChain / Dify），每一层都能讲清底层实现；架构参考 [Open WebUI](https://github.com/open-webui/open-webui) 拆解重建。

## 核心能力

- **知识库问答（RAG）**：建库 → 上传文件 → 切片向量化 → 混合检索（向量余弦 + BM25 经 RRF 融合）→ 可选 bge-reranker 重排 → 带 `[序号]` 引用来源回答；库外问题明确拒答，不编造
- **文档解析**：txt / md / pdf / docx 文本抽取；扫描件、复杂表格可选接入 PaddleOCR PP-StructureV3 输出版面感知 Markdown，服务不可达时优雅降级
- **研发/运维 Agent 工具**：日志分析（级别统计/异常归因/排查建议）、Git diff 变更摘要与风险点、工单结构化总结、测试用例生成、联网搜索（可选，DuckDuckGo 免 key，失败优雅降级）
- **RAG × Agent 融合**：Agent 自主决定调用 `search_knowledge` 检索知识库，全过程写入运行日志（`agent_runs` / `agent_steps`），前端可展开查看每一步
- **MCP Server**：知识库检索与研发/运维工具经官方 `mcp` SDK 暴露为标准 MCP 服务（stdio），Cursor / Claude Desktop 配置后可在 IDE 里直接查企业知识库
- **多模型接入**：Ollama（原生 `/api/chat`，NDJSON 自动转 OpenAI SSE）与任意 OpenAI Compatible 接口，前端只维护一种流解析
- **移动端入口**：Android WebView 壳 + JS 桥接原生语音输入（STT）、语音播报（TTS）、文件选择、安全区适配
- **长期记忆**：手动维护偏好/事实/项目记忆，按开关注入 Agent 上下文
- **LLM 异步增强**：对话标题自动生成、回答后追问建议 chip（点击即问），失败静默不阻塞聊天
- **全量持久化**：对话、配置、文件、知识库、向量、Agent 日志全部落 SQLite，重启不丢

## 界面预览

| 知识库问答（引用来源） | Agent 日志分析 |
|---|---|
| ![知识库问答带引用来源](docs/images/chat-citations.png) | ![Agent 日志分析](docs/images/agent-log-analysis.png) |

| 移动端·知识库管理 | 移动端·对话 |
|---|---|
| ![移动端知识库管理](docs/images/mobile-knowledge.png) | ![移动端对话](docs/images/mobile-chat.png) |

**演示视频**：[5 分钟完整演示 demo.mp4 —— RAG 引用/拒答 + Agent 工具 + Docker 部署](https://github.com/ng520tx/MyOpenWeb/releases/download/v0.1.0/demo.mp4)（35MB，点击即可播放/下载）

## 总体架构

```mermaid
flowchart TD
    subgraph mobile [移动端入口]
        Android[Android WebView 壳]
        H5[React H5 聊天页]
    end
    subgraph backend [FastAPI 本地后端]
        ChatRouter[chat_proxy 聊天入口]
        AgentRouter[agent Agent循环]
        FilesRouter[files 文件服务]
        KnowRouter[knowledge 知识库服务]
        RAG[rag 检索/切片]
        Embed[embeddings 向量化]
        Tools[agent_tools 工具集]
        Ocr[ocr_client OCR解析]
    end
    subgraph store [SQLite 存储]
        Chats[(chats)]
        FilesTbl[(files)]
        Knowledge[(knowledge / knowledge_file)]
        Chunks[(chunks + embedding)]
    end
    Models[Ollama / OpenAI 模型]
    OcrSvc[PP-StructureV3 OCR服务]

    Android --> H5
    H5 --> ChatRouter
    H5 --> AgentRouter
    H5 --> FilesRouter
    H5 --> KnowRouter
    ChatRouter --> RAG
    AgentRouter --> Tools
    AgentRouter --> RAG
    KnowRouter --> RAG
    RAG --> Chunks
    RAG --> Embed
    Embed --> Models
    FilesRouter --> FilesTbl
    FilesRouter --> Ocr
    Ocr --> OcrSvc
    KnowRouter --> Chunks
    ChatRouter --> Models
    AgentRouter --> Models
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript 5 + Vite 5 + Tailwind CSS 3 + Zustand |
| 后端 | Python 3.12 + FastAPI + SQLite（内置 sqlite3，向量存 JSON + numpy 余弦检索） |
| 模型 | Ollama（默认 `qwen3.5:4b` 对话 / `bge-m3` 向量化）或任意 OpenAI Compatible |
| OCR（可选） | PaddleOCR PP-StructureV3，独立 venv 独立服务，CPU 可跑 |
| 移动端 | Kotlin + WebView（API 26+），JS 桥接原生能力 |

## 快速开始

前置：Python 3.12、Node 18（见 `.nvmrc`）、pnpm、[Ollama](https://ollama.com)。

```bash
# 1. 拉取模型
ollama pull qwen3.5:4b
ollama pull bge-m3

# 2. 后端（首次自动建 venv 装依赖）
#    Windows：双击 start-backend.bat，或
powershell -ExecutionPolicy Bypass -File scripts/dev-server.ps1
#    WSL/Linux：
python3 -m venv .venv && ./.venv/bin/pip install -r server/requirements.txt
pnpm dev:server

# 3. 前端
pnpm install
pnpm dev
```

打开 `http://localhost:5173`：设置里点「测试连接」确认模型可达 → 顶部「知识库」建库并上传文档 → 「建立/重建索引」→ 「聊天使用」选中后提问即可看到带引用来源的回答。

可选 OCR 服务（扫描件/表格解析）：`powershell -ExecutionPolicy Bypass -File scripts/ocr-server.ps1`，然后在设置里开启「OCR 文档解析」。

### Docker 一键部署

```bash
# 模型服务用宿主机已有的 Ollama（默认）
docker compose up -d --build

# 或者连 Ollama 一起编排
PROVIDER_BASE_URL=http://ollama:11434/v1 docker compose --profile ollama up -d --build
docker compose exec ollama ollama pull qwen3.5:4b
docker compose exec ollama ollama pull bge-m3
```

容器内 FastAPI 直接托管构建好的 H5，打开 `http://localhost:8000` 即可使用；数据持久化在 `myopenweb-data` 卷。

### MCP Server（在 Cursor 里直接查企业知识库）

知识库检索与研发/运维工具已通过官方 `mcp` SDK 暴露为标准 MCP 服务（stdio transport）。Cursor 用户在 `~/.cursor/mcp.json`（或项目 `.cursor/mcp.json`）加入：

```json
{
  "mcpServers": {
    "myopenweb": {
      "command": "wsl.exe",
      "args": ["bash", "-lc",
        "cd /mnt/d/ai_one/MyOpenWeb && ./.venv/bin/python -m server.mcp_server.main"]
    }
  }
}
```

Linux/macOS 直接 `command: "/path/to/.venv/bin/python"` + `args: ["-m", "server.mcp_server.main"]`。工具清单：`search_knowledge`（混合检索全链路）、`list_knowledge_bases`、`analyze_log`、`summarize_git_diff`、`summarize_ticket`、`generate_test_cases`。协议冒烟：`python -m server.eval.mcp_smoke`。

## 检索质量评测

自建评测集（3 份企业文档语料、40 条 QA 对，见 `server/eval/`），Hit@K 与 MRR 实测（bge-m3 向量，CPU 环境，完整报告见 [server/eval/results.md](server/eval/results.md)）：

| 检索模式（chunk_size=600） | Hit@1 | Hit@4 | MRR | 平均耗时 |
|---|---|---|---|---|
| 纯向量余弦 | 0.82 | 0.97 | 0.887 | 675 ms |
| 混合检索（BM25 + 向量 RRF） | 0.93 | 0.97 | 0.955 | 736 ms |
| 混合检索 + bge-reranker | 1.00 | 1.00 | 1.000 | 5245 ms（CPU） |

结论：BM25 融合对命令、编号、术语类运维问题的首位命中提升明显（+11pp）；rerank 进一步把首位命中拉满，但 CPU 推理延迟显著，适合质量优先场景，在线低延迟场景建议 GPU 或缩小候选池。评测可复现：

```bash
MYOPENWEB_DATA_DIR=server/eval/.data python -m server.eval.run_eval
```

**多轮对话检索改写**（8 条指代型追问，如"它的端口是多少"，报告见 [server/eval/results-multiturn.md](server/eval/results-multiturn.md)）：

| 指标 | 原始追问直接检索 | LLM 改写后检索 |
|---|---|---|
| Hit@1 | 0.62 | 0.88 |
| MRR | 0.792 | 0.938 |

多轮追问经常丢失主语（"它的端口"），检索前用对话历史把问题改写为自包含查询（qwen2.5:3b，改写失败自动回退原文），首位命中提升 26pp。复现：`python -m server.eval.run_multiturn_eval`。

**生成质量评测（LLM-as-judge）**：检索之外也评"答得好不好"。等距抽 12 条 QA，生成（qwen2.5:3b）与评审（qwen3.5:4b）分离打分，维度对应 RAGAS 的 faithfulness / answer relevancy（报告见 [server/eval/results-judge.md](server/eval/results-judge.md)）：

| 指标 | 平均分（1–5） |
|---|---|
| Faithfulness（是否忠于检索资料，拒答计忠实） | 4.00 |
| Answer Relevancy（是否切中问题） | 4.17 |

复现：`python -m server.eval.run_judge_eval`。低分样例集中在小模型引用编号错乱，生产建议换更强评审模型并人工复核低分回归。

**检索自纠错（Agentic Retrieval）开/关对照**：检索后先让模型判断资料是否足以回答（Grader），不足时按缺失信息重检索一轮再合并（上限 1 次）。标准 40 条集上基线 Hit@4 已 0.97，Grader 仅触发 1/40、指标持平；在 12 条口语化措辞的困难集上（top_k=2，报告见 [server/eval/results-agentic-hard.md](server/eval/results-agentic-hard.md)）：

| 指标 | 单轮检索 | 自纠错检索 |
|---|---|---|
| Hit@4 | 0.83 | 0.92 |
| MRR | 0.708 | 0.736 |

收益集中在"用户口语与文档书面语措辞错位"的查询（Grader 会生成换表述的补充查询）；代价是每次多一个 Grader 请求。默认关闭，设置页可开。复现：`python -m server.eval.run_agentic_eval`。

## 核心设计与取舍

- **为什么自研 RAG / Agent 而不用 LangChain、Dify**：目标是把检索与工具调用的每一步（切片策略、相似度计算、拒答规则、工具循环上限、运行日志）做成可解释、可调试的白盒；规模上来后再按接口替换为框架或向量库，`repositories` 层已预留切换点。
- **向量为什么存 SQLite**：个人/小团队规模下，`chunks` 表存 JSON 向量 + numpy 内存余弦已足够（百级文档毫秒级响应），省去向量库部署成本，正好匹配"企业内网轻量私有化"场景；预留 PostgreSQL + pgvector 迁移方案。
- **中文 BM25 分词**：FTS5 的 unicode61 分词器会把整段中文当成一个 token。方案是自实现 CJK 字符二元组 + 英文小写单词的轻量分词（`services/tokenize.py`），零额外依赖即可让 BM25 在中文语料上工作，规模上来可替换 jieba。
- **rerank 可降级**：cross-encoder 依赖（torch）单独隔离在 `server/rerank/requirements.txt`，未安装或模型加载失败时自动回退为融合排序并做负缓存，核心链路永不因 rerank 阻塞。
- **防幻觉**：强约束 system prompt（只依据参考资料回答）+ 引用来源展示 + 检索未命中时明确拒答 + 换 embedding 模型导致维度不一致时拒用旧索引并提示重建。
- **可观测性**：Agent 每轮的模型判断、工具调用、工具结果、最终回答全部落库，`GET /api/agent/runs/{id}` 可回放，前端可展开。
- **工具安全**：工具由后端白名单实现，模型只能表达"调用意图"，不能执行任意代码；计算器用表达式解析器而非 `eval`。
- **协议统一**：Ollama NDJSON、OpenAI SSE 在后端统一转换为 OpenAI SSE，前端只有一条流解析路径。

## 项目结构

```text
├── android/          # Android WebView 壳（Kotlin，STT/TTS/文件/安全区桥接）
├── server/           # FastAPI 后端（routers / services / repositories / schemas 分层）
│   ├── services/     # providers / rag / embeddings / agent_runner / agent_tools / file_extract / ocr_client
│   └── ocr/          # 可选 PaddleOCR 独立服务依赖
├── src/              # React H5（apis / components / stores / bridge）
├── scripts/          # 一键启动脚本（后端 / OCR）
└── docs/             # 架构文档、RAG+Agent 模块文档、Open WebUI 对照分析、排障手册
```

## 文档

- [项目架构](docs/project-architecture.md)：技术栈、数据流、数据库设计、Bridge 协议
- [RAG + Agent 模块](docs/rag-agent-copilot.md)：能力总览、API 参考、使用步骤、设计取舍
- [Open WebUI 对照分析](docs/open-webui-analysis.md)：参考项目的拆解与借鉴边界
- [排障手册](docs/troubleshooting.md)

## Roadmap

- [x] RAG 知识库（切片 / 向量化 / topK / 引用 / 拒答）
- [x] 研发/运维 Agent 工具 + 运行日志
- [x] PaddleOCR 扫描件解析（可选服务）
- [x] 混合检索（BM25 + 向量 RRF 融合）与 bge-reranker 重排
- [x] 检索质量评测（Hit@K / MRR 参数对照，见 `server/eval/`）
- [x] Docker 一键部署（FastAPI 托管 H5 单容器）
- [x] 后端单元测试 + GitHub Actions CI
- [x] Agent 中间过程流式推送（思考 / 工具调用 / 工具结果实时时间线）
- [x] 多轮对话检索改写（query rewrite，Hit@1 +26pp）
- [x] MCP Server（知识库 + 工具暴露为标准 MCP 服务，Cursor 可直连）
- [x] 检索自纠错（Grader 评估 + 有界重检索，开/关对照评测）
- [x] Agent 联网搜索工具（ddgs 免 key，可选开关 + 优雅降级）
- [x] LLM 对话标题生成 + 追问建议 chip（异步增强）
- [ ] PostgreSQL + pgvector 可切换向量后端

## License

MIT
