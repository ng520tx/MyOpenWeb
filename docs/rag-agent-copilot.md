# 企业研发/运维 AI Copilot（RAG + Agent）功能模块

> 本文档覆盖 RAG 知识库与研发/运维 Agent 工具这一功能模块的：能力总览、架构、数据流、API、使用步骤、求职作品包装（简历/面试/一页介绍/演示脚本）、以及后续扩展预案。
> 通用项目架构见 `docs/project-architecture.md`，常见问题见 `docs/troubleshooting.md`。

## 1. 能力总览

把原本的「本地聊天骨架」补齐成可作为求职作品的「企业研发/运维 AI Copilot 工作台」，新增自研能力：

1. 文件落盘 + 文本抽取：上传 txt/md/pdf/docx/图片，后端抽取纯文本并落盘（PDF/扫描件/图片可选走 PaddleOCR），独立 `files` 表。
2. RAG 知识库：建库 → 挂文件 → 切片向量化 → 多轮检索改写（query rewrite）→ 混合检索（向量余弦 + BM25 经 RRF 融合，可选 bge-reranker 重排）→ 带引用回答 → 库外问题拒答。
3. 研发/运维 Agent 工具：日志分析、Git diff 摘要、工单总结、测试用例生成，并能让 Agent 自己决定调用 `search_knowledge` 查知识库；思考/工具调用/工具结果全过程经 SSE 实时推送，前端渲染步骤时间线。
4. 检索质量评测：自建 40 条 QA 评测集 + 8 条多轮指代追问集，Hit@K / MRR / 延迟跨参数对照（见第 7 节）。
5. 框架认知对照：`examples/langgraph-agent/` 用 LangGraph 复刻同等 Agent 能力，沉淀"手写循环 vs 框架"的对比结论（见第 10 节）。

全程自研、零额外服务部署（向量直接存 SQLite，BM25 用 SQLite 内置 FTS5，内存余弦检索），便于面试讲清底层，也便于小规模私有部署。

## 2. 架构

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

### 关键设计取舍

- 向量存 SQLite：`chunks.embedding` 存 JSON 数组，查询时用 numpy 内存余弦相似度。个人/演示规模足够，省去额外向量库部署。
- BM25 用 SQLite FTS5：零新增服务。中文分词用自研 CJK 二元组 + 英文小写单词（`services/tokenize.py`），解决 unicode61 分词器把整段中文当一个 token 的问题；索引和查询走同一分词器保证匹配一致。
- 混合检索用 RRF：向量排名与 BM25 排名按 `1/(60+rank)` 融合，天然免调权重、对分数尺度不敏感；候选池取 `max(top_k*3, 10)` 给融合与重排留空间。
- rerank 可降级：cross-encoder（bge-reranker）依赖单独放 `server/rerank/requirements.txt`，未安装或模型加载失败时负缓存 + 自动回退融合排序，核心链路不因 rerank 阻塞。
- 两种工具协议可切换（设置 → Agent）：`prompt` 用系统提示词约定 JSON 输出，任何能写 JSON 的模型都能跑（含不支持 tools 的小模型），脏输出有归一化容错；`native` 走模型原生 function calling（tools 参数 + tool_calls 响应 + role=tool 回填），格式更稳、省去协议说明的 token，但依赖模型端支持（qwen2.5 实测可用）。
- 不用 Dify：RAG 与 Agent 都自研，面试更好讲底层；Dify 仅作为后期可选编排 provider 的扩展点。
- 普通聊天 vs Agent 两条 RAG 路径：
  - 关闭 Agent + 选了知识库 → `/api/chat/completions`，后端直接检索并把片段注入 system_prompt（确定性强）。
  - 开启 Agent + 选了知识库 → `/api/agent/completions`，把 `search_knowledge` 作为工具交给模型自主调用（更智能体化）。
- 无答案拒答：检索为空时注入"知识库中没有找到相关信息"的拒答提示，避免幻觉。
- 维度保护：换了 embedding 模型导致向量维度不一致时，检索返回空并提示重建索引。

## 3. 核心数据流

### 3.1 文件上传 + 抽取

```text
选择文件 → POST /api/files (multipart)
→ file_extract.extract_text()（pdf=pypdf / docx=python-docx / 其余按文本解码）
→ 落盘 server/data/files/<id><ext>，元数据与文本写入 files 表
→ 返回 FileRecord（含 text_preview / text_length）
```

### 3.2 建立索引

```text
知识库绑定文件 → POST /api/knowledge/{id}/index
→ 取出每个文件的 text_content
→ rag.split_text() 按字符 + 自然边界 + overlap 切片
→ embeddings.embed_texts() 分批向量化（默认 16/批）
→ replace_chunks() 原子替换该知识库的全部 chunks
→ 返回 {files, chunks, embedding_model}
```

### 3.3 检索增强问答

```text
聊天带 knowledge_id → chat_proxy
→ rag.retrieve_for_chat()：取最后一条用户消息为 query
→ 多轮对话时先 query_rewrite.rewrite_query()：
   用最近 3 轮历史把"它的端口是多少"这类省略主语的追问改写成自包含查询
   （一次 temperature=0 的小请求；失败/超长/空输出自动回退原文）
→ query_knowledge()：
   1) 向量化 query，numpy 余弦得到向量排名
   2) hybrid 模式再取 BM25（FTS5）排名，RRF 融合
   3) 开启 rerank 时对候选池做 cross-encoder 重排（失败自动回退）
→ 命中：拼"带 [序号] 来源标注的参考资料"system_prompt + 返回 sources
→ 未命中：注入拒答提示
→ 流式响应前先 emit 一条 {"sources":[...]} SSE，前端展示"引用来源"
```

检索模式与 rerank 在「设置 → 知识库 / RAG」配置；`POST /api/knowledge/{id}/query` 支持 `mode` / `rerank` 覆盖参数做 A/B 调试。切换 hybrid 后需重建索引以生成 BM25 词表。

### 3.4 Agent 调用知识库

```text
Agent 模式 + knowledge_id → agent_runner
→ 工具列表追加 search_knowledge
→ run_agent_events() 逐步产出事件：
   thinking（每轮决策前）/ tool_call（带参数）/ tool_result（带摘要与 ok 状态）
→ 事件实时包成 SSE agent_event 帧推给前端（空 delta，老客户端自动忽略）
→ 模型决定调用 search_knowledge(query, top_k)
→ 后端异步 query_knowledge()，把片段回填给模型
→ 命中片段去重后作为 sources 一并返回；agent_steps 记录完整输入输出
→ 前端生成中渲染"思考中 / 调用工具 / 工具完成"时间线，完成后可查看完整运行日志
```

## 4. API 参考

### 文件 `/api/files`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/files` | 文件列表（元数据 + 文本预览） |
| POST | `/api/files` | multipart 上传，抽取文本并落盘 |
| GET | `/api/files/{id}` | 文件详情（含全文 `text_content`） |
| POST | `/api/files/{id}/reextract` | 对已存文件重新抽取（开启 OCR 后回填新文本，需随后重建索引） |
| DELETE | `/api/files/{id}` | 删除文件（含磁盘文件） |

### 知识库 `/api/knowledge`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/knowledge` | 知识库列表（含文件数/分块数） |
| POST | `/api/knowledge` | 新建知识库 |
| GET | `/api/knowledge/{id}` | 知识库详情（含文件列表） |
| PUT | `/api/knowledge/{id}` | 改名/改描述 |
| DELETE | `/api/knowledge/{id}` | 删除知识库（级联 chunks/绑定） |
| POST | `/api/knowledge/{id}/files` | 绑定文件 `{file_id}` |
| DELETE | `/api/knowledge/{id}/files/{file_id}` | 解绑文件 |
| POST | `/api/knowledge/{id}/index` | 建立/重建索引 |
| POST | `/api/knowledge/{id}/query` | 调试检索 `{query, top_k}` |

### 聊天 / Agent 扩展

- `POST /api/chat/completions` 与 `POST /api/agent/completions` 新增可选字段：`knowledge_id`、`rag_top_k`。
- 流式响应中通过 `data: {"sources":[...]}` 事件回传引用来源（前端 `streaming.ts` 解析 `parsed.sources`）。

## 5. 使用步骤（本地）

1. 安装后端依赖（新增 `python-multipart`、`pypdf`、`python-docx`、`numpy`）：
   ```bash
   ./.venv/bin/pip install -r server/requirements.txt
   ```
2. 拉取 embedding 模型（Ollama，默认 `bge-m3`，适合中文）：
   ```bash
   ollama pull bge-m3
   ```
   如需更轻量可改用 `nomic-embed-text`，并在「设置 → 知识库 / RAG → Embedding 模型」里填写后点"保存连接配置到后端"。
3. 启动后端与前端：`start-backend.bat` / `pnpm dev:server` + `pnpm dev`。
4. 顶部导航点「知识库」图标 → 新建知识库 → 上传文件 → 点「建立 / 重建索引」。
5. 在知识库列表点「聊天使用」选中该库（导航栏出现"知识库"标记），回到聊天提问。
6. 回答下方点「引用来源」即可看到命中的文件与片段；问库外问题会拒答。
7. 想体验智能体路径：在设置里开启「Agent 模式」，再选知识库提问，Agent 会自己调用 `search_knowledge`，可展开"Agent 调用工具"查看过程。

## 6. 求职作品包装

### 6.1 简历项目描述（可直接粘贴）

**建议简历标题**（任选其一，按目标岗位调整）：移动端 AI 应用工程师 / AI Agent 应用工程师 / AI 应用工程化工程师。

**项目段落（精简版，适合一行项目栏）**：

> 企业研发/运维 AI Copilot 工作台（独立设计与实现）：Android 原生壳 + React H5 流式聊天 + 自研 RAG 知识库（混合检索 + rerank + 自建评测）+ 工具型 Agent，FastAPI 分层后端、多模型适配、Docker 一键私有化部署，用于知识问答、运维排障与研发提效。

**项目段落（完整版，可直接粘贴）**：

> 独立设计并实现「企业研发/运维 AI Copilot 工作台」：Android 原生壳 + React H5 流式聊天 + WebView 桥接（语音输入/播报、文件选择、安全区），FastAPI 本地后端分层（routers/services/repositories/schemas），统一 OpenAI SSE，接入 Ollama / OpenAI Compatible 多模型。自研 RAG 全链路：文件落盘与 txt/md/pdf/docx/扫描件（PaddleOCR）文本抽取、切片、向量化、混合检索（BM25+向量 RRF 融合，自研中文分词适配 SQLite FTS5）、可选 bge-reranker 重排、引用来源标注、库外问题拒答；自建 40 条 QA 评测集量化调优（混合检索使 Hit@1 提升 11pp 至 0.93，rerank 后 MRR 达 1.00）。实现研发/运维 Agent 工具（日志分析、Git diff 摘要、工单总结、测试用例生成）并与 RAG 融合（Agent 自主调用 `search_knowledge`，全过程写入运行日志）。pytest 单测 + GitHub Actions CI + Docker 多阶段构建一键私有化部署。

**如何结合你的真实经历讲（重要，别写成通用项目）**：

- 用 19 年研发与「掌上运维 / 装机助手 / 故障中心 / 资源中心」的背景，把这个产品定位成"我最懂的企业运维/研发场景"的 AI 落地，而不是泛泛的聊天机器人。
- Android + H5 + WebView 桥接是你的差异化护城河——市场上纯做 RAG 的人很多，但"能把 AI 做进移动端、还懂企业系统联调与线上排查"的人少。
- Agent 工具（日志分析、Git diff 摘要、工单总结）直接对应你过去做线上问题排查、版本变更、工单处理的真实经验，面试时用真实案例讲会非常可信。
- 善用 Cursor/Codex/Claude Code：可以讲"用 AI Coding 工作流把这个产品从 0 到 1 独立交付"，正好对上"AI Coding / 研发效能"岗位。

**可量化的点（按真实情况填）**：知识库文件数 / 分块数（如 193 块）、检索 topK 与响应时延、支持的文件类型数（4 种）、Agent 工具数（4+1）、从 0 到 1 的交付周期（如 4 周）。

### 6.2 面试话术（高频问题）

- **整体架构一句话**：移动端（Android 壳 + React H5 流式）→ FastAPI 分层后端（routers/services/repositories/schemas，统一 OpenAI SSE）→ 自研 RAG（混合检索 + rerank + 评测）+ 工具型 Agent → 多模型（Ollama / OpenAI Compatible），数据全落 SQLite，Docker 一键私有部署。
- **RAG 是怎么实现的？**：文本抽取 → 按字符 + 自然边界 + overlap 切片 → embedding 批量向量化入库（SQLite 存 JSON 向量）→ 查询时向量余弦排名，hybrid 模式再融合 BM25（FTS5）排名（RRF），可选 cross-encoder 重排 → 把命中片段带 `[序号]` 来源拼进 system_prompt → 让模型只依据资料回答，未命中则拒答。
- **混合检索为什么用 RRF 而不是加权分数？**：向量余弦和 BM25 分数量纲不同，直接加权要调参且对分布敏感；RRF 只用排名（`1/(60+rank)`），免调权、稳健，是业界常用融合方式。实测比纯向量 Hit@1 提升 8~11pp。
- **中文 BM25 怎么处理分词？**：SQLite FTS5 的 unicode61 会把整段中文当一个 token。自研轻量分词（CJK 字符二元组 + 英文小写词），索引与查询同一分词器，零依赖；规模大再换 jieba。
- **Rerank 为什么有用？代价是什么？**：召回阶段（双塔/BM25）是"各自编码再比较"，rerank 用 cross-encoder 对"问题-片段"拼接后整体打分，捕捉细粒度交互，所以首位命中显著提升（实测 Hit@1 0.93→1.00）。代价是每个候选都要过一遍模型，CPU 上单次检索到 5s 量级，因此做成可开关 + 失败自动回退，在线低延迟场景建议 GPU/ONNX/缩小候选池。
- **检索质量怎么评的？**：自建 40 条 QA 评测集（三份企业文档语料），指标 Hit@1/4/8 与 MRR，另测端到端检索延迟（含查询向量化）；跑 chunk_size × 检索模式 × rerank 全参数对照，报告落盘可复现（`server/eval/`）。
- **为什么不用向量数据库 / Dify？**：个人/演示规模 SQLite + 内存余弦足够，且能讲清每一步；强调"自己写的"比"拖流程"更有说服力。架构上预留了 PostgreSQL + pgvector 与 Dify provider 扩展点，规模上来按接口替换实现即可。
- **怎么防幻觉 / 保证可信？**：强约束 system_prompt（只用参考资料、未命中明确说不知道）、返回引用来源给前端展示、embedding 维度不匹配时拒绝用旧索引并提示重建。
- **Agent 和普通 RAG 的区别？**：普通 RAG 是后端确定性检索后注入 system_prompt（结果稳定、好复现）；Agent 把检索做成 `search_knowledge` 工具，由模型自主决定是否检索、检索什么，并记录工具调用日志，更接近"智能体"。两种路径按场景选用。
- **prompt-based 和原生 function calling 的区别？**（两种都实现了，可切换）：prompt 协议把工具说明写进系统提示词、约定 JSON 输出，兼容任何模型，但要自己做解析与容错（小模型经常输出 `{"action":"calculator",...}` 这类脏格式）；native 协议把 tools schema 直接传给模型端接口，返回结构化 `tool_calls`、按 `role=tool` 回填，格式稳定、少烧协议 token，但要求模型支持（qwen2.5 支持，很多小模型不支持）。生产上建议：模型可控时优先 native，兜底 prompt。
- **多轮对话检索为什么会失效？怎么解决？**：追问经常省略主语（"它的端口是多少"），原文检索时 BM25 与向量都缺少可区分关键词。解决：检索前用当前模型把"最近 3 轮历史 + 追问"改写成自包含查询（temperature=0 小请求），实测 8 条指代型追问 Hit@1 从 0.62 到 0.88；改写失败自动回退原文，链路不受影响。
- **（加分，体现迭代）两条路径的拒答怎么保持一致？**：最初 Agent 模式拒答偏松，问库外问题会用通用知识发挥；后来在"选中知识库"时给 Agent 注入了拒答约束（检索为空或不相关就明确说"知识库中没有找到相关信息"），让 Agent 路径与普通 RAG 路径的拒答行为统一。这是从实测里发现并修掉的问题，能体现工程迭代意识。
- **切片大小/overlap 怎么定的？**：按字符切并优先在自然边界（段落/句子）断开，留 overlap 防止答案被切断；可按文档类型调参。讲清"为什么不是越大越好/越小越好"的权衡即可。
- **工程化体现在哪？**：分层后端、统一 SSE 协议、Provider/embedding 的 WSL→Windows 主机回退、运行日志可观测、依赖可降级（缺 pdf/docx 库时报清晰错误而非崩溃）、配置持久化到后端。
- **移动端怎么接的？**：Android WebView 壳 + JS 桥（moaBridge）打通语音输入/TTS 播报/文件选择/安全区；H5 走统一后端 SSE，和桌面端共用一套接口。这是我相对纯算法/纯后端候选人的差异化优势。

### 6.3 一页产品介绍

- 名称：企业研发/运维 AI Copilot 工作台
- 定位：面向研发、运维、交付团队的移动端 AI 助手
- 核心能力：知识库问答（带引用、可拒答）、日志分析、故障排查、接口/工单理解、测试用例生成、代码变更摘要、语音交互
- 技术亮点：移动端原生壳 + H5 流式、自研 RAG、工具型 Agent、多模型适配、全本地可私有部署
- 适用场景：企业内网知识问答、运维排障、研发提效、传统企业轻量私有化

### 6.4 演示视频脚本（3–5 分钟，可照着录）

> 重要：演示「严格拒答」用普通模式（关闭 Agent），库外问题会干净拒答；演示「智能体」再开 Agent 模式。
> 知识库内容建议：岗位定位是研发/运维 Copilot，演示时最好用「运维手册 / 接口文档 / 故障案例」做知识库更贴合；现有「药品手册」可作为第二个垂直案例。下面脚本两种内容都适用，括号里给出基于现有药品库的示例问法。
> 现成素材（`examples/` 目录，可直接上传/粘贴）：`ops-manual.md` 运维手册 + `api-reference.md` 接口文档 + `faq-onboarding.md` 新人 FAQ 建知识库；`error.log` 演示日志分析；`sample.diff` 演示 Git diff 摘要。库内问题可直接用 `server/eval/dataset.jsonl` 里的问法（如"数据库连接池耗尽时的处置步骤？"）。

#### 录制前检查清单（30 秒过一遍）

- [ ] 后端 8000 / 前端已启动，`/api/health` 返回 `{"ok":true}`
- [ ] 设置里 Provider 已连通、模型已选好、Embedding 模型=`bge-m3`，已点过「保存连接配置到后端」
- [ ] 检索模式确认（默认混合检索；如要演示 rerank 需先装 `server/rerank/requirements.txt` 依赖）
- [ ] 目标知识库已「建立/重建索引」，列表显示分块数
- [ ] 新建一个干净对话，避免历史串味
- [ ] 准备好 2 段素材：`examples/error.log`、`examples/sample.diff`（贴进输入框即可）

#### 分镜脚本

1. 开场（约 20s）：一句话定位"面向研发/运维团队的移动端 AI 助手，知识库问答 + 工具型 Agent，全自研、可私有部署" → 手机/H5 打开，随便问一句展示流式输出与语音按钮。
2. 知识库问答 + 引用（约 70s，**普通模式**）：
   - 顶部「知识库」→ 展示已建库、上传的文件列表与分块数 → 点「聊天使用」选中（导航栏出现"知识库"标记）。
   - 问一个**库内**问题（示例："坎地沙坦胶片有什么用？""蒙脱石散有什么注意事项？"）→ 得到回答后点开「引用来源」，展示命中的文件名与片段。
3. 库外拒答（约 30s，**普通模式**）：问一个明显**库外**问题（示例："你知道建筑历史吗？""今天天气怎么样？"）→ 展示模型明确回答"知识库中没有找到相关信息"，强调"不乱编"。
4. 研发/运维 Agent 工具（约 80s，**开启 Agent 模式**）：
   - 点「日志分析」快捷按钮，贴入异常日志 → 得到结构化的错误级别/异常类型/根因与排查建议。
   - 点「Git diff 摘要」，贴入一段 diff → 得到变更文件、增删行、风险点。
   - 展开「Agent 调用工具」查看本轮调用过程。
5. RAG × Agent 融合（约 40s，**Agent 模式 + 选中知识库**）：问库内问题 → 展示 Agent 自主调用 `search_knowledge`、回答带「引用来源」，并能展开看工具调用；再问一个库外问题，展示同样会拒答（已统一两条路径的拒答行为）。
6. Docker 部署收尾（约 30s）：
   - 切到终端（仓库根目录），敲 `docker compose up -d --build` → 等它输出 `Container ... Started`（如果之前构建过，几秒就完成；录制前可先 `docker compose down` 让这条命令有过程感）。
   - 敲 `curl http://localhost:8000/api/health` 显示 `{"ok":true}`，浏览器打开 `http://localhost:8000` 展示同一个应用已经在容器里跑起来。
   - 口播："整套应用一条 docker compose up 就能部署到企业内网，前端构建、后端服务打进同一个镜像，数据落在独立数据卷里。"
7. 架构小结（约 20s）：一句话（移动端壳 + H5 流式 + FastAPI 分层 + 自研 RAG + 工具型 Agent + 多模型）+ 强调"全自研、零额外服务、可私有部署"。

#### 旁白可直接念的关键句

- "检索命中时回答带可点击的引用来源；问知识库以外的问题会直接拒答，避免幻觉。"
- "Agent 模式下，检索被封装成 `search_knowledge` 工具，由模型自己决定何时查、查什么，整个调用过程有日志可回溯。"
- "整套 RAG 和 Agent 都是自研的，向量直接存 SQLite、用 numpy 算余弦相似度，不依赖外部向量库或编排平台，方便企业内网私有部署。"
- "检索走混合链路：BM25 关键词加向量语义经 RRF 融合，再可选 bge-reranker 重排；我自建了 40 条 QA 的评测集，混合检索比纯向量首位命中提升 11 个百分点。"

## 7. 检索质量评测

评测材料在 `server/eval/`：`dataset.jsonl` 40 条 QA（覆盖运维手册、接口文档、新人 FAQ 三份演示语料 `examples/*.md`），`run_eval.py` 跑 chunk_size × 检索模式 × rerank 的全参数对照，输出 Hit@1/4/8、MRR、平均与 P95 检索延迟。

运行（后端 venv + Ollama bge-m3 就绪后）：

```bash
MYOPENWEB_DATA_DIR=server/eval/.data python -m server.eval.run_eval
# 数据沙箱在 server/eval/.data，不污染正式库；报告写入 server/eval/results.md
```

最近一次实测结论（CPU 环境，完整表见 `server/eval/results.md`）：

- 混合检索比纯向量的 Hit@1 提升 8~11 个百分点（命令、编号、术语类问题受益最大），延迟仅增加约 50ms。
- rerank（bge-reranker-base）把 chunk_size=600 的 Hit@1 从 0.93 拉到 1.00，但 CPU 推理让单次检索到 5s 量级——质量优先场景可开，在线低延迟场景建议 GPU / ONNX / 缩小候选池。
- chunk_size 400/600/800 中，600 在该语料上是质量与块数的平衡点。

面试可讲的点：评测集怎么建、Hit@K 与 MRR 怎么算、RRF 为什么免调权、rerank 的收益与代价、为什么中文 BM25 需要自己分词。

## 8. OCR 文档解析（PP-StructureV3）

针对扫描件/图片型 PDF、复杂表格、印章等 `pypdf` 抽不出内容的场景，新增一条可选的 OCR 解析通道。

### 设计取舍
- OCR 作为**独立本地服务**（PaddleOCR PP-StructureV3，CPU 可跑），后端通过 HTTP 调用，复用 Ollama 那套“可配置 URL + WSL→Windows 主机回退”。
- **主后端依赖保持精简**：paddle 相关依赖只装在独立 venv（`server/ocr/requirements.txt`），不进 `server/requirements.txt`，后端启动不受影响。
- **默认关闭、优雅降级**：未开启或服务不可达时退回 `pypdf`，上传永不失败（失败仅记一条 warning）。
- **触发模式**：`auto`（仅当 pypdf 文本为空/过短、判定为扫描件时才 OCR）/ `always`（PDF、图片都走 OCR）。
- **输出版面感知 Markdown**（保留标题/表格/阅读顺序），再喂给现有 `rag.split_text` 切片，提升召回质量。

### 相关文件
- `server/services/ocr_client.py`：base64 调用 PP-StructureV3 serving 的 `POST /layout-parsing`，解析 `result.layoutParsingResults[].markdown.text` 拼成全文。
- `server/services/file_extract.py`：`extract_text_async()` 按文件类型/模式决定是否走 OCR；图片类型必须开启 OCR 才解析。
- 配置项：`ocr_enabled` / `ocr_base_url`（默认 `http://localhost:8118`）/ `ocr_mode`，存于 `app_config`；前端在“设置 → 知识库 / RAG → OCR 文档解析”填写后点“保存连接配置到后端”。

### 启动 OCR 服务（独立 venv）
- Windows：`powershell -ExecutionPolicy Bypass -File scripts/ocr-server.ps1`
- WSL/Linux：`bash scripts/ocr-server.sh`
- 首次会建 `server/ocr/.venv` 并安装 `paddlepaddle` + `paddleocr`（约几百 MB，需联网），服务监听 `:8118`。确切 serving CLI 可能随 PaddleOCR/PaddleX 版本变化，失败时查官方 serving 文档。

### 使用步骤
1. 启动 OCR 服务（见上）。
2. 设置里开启“OCR 文档解析”，填服务地址与模式，保存到后端。
3. 新上传的 PDF/图片会按模式自动走 OCR；**已上传的文件**可在知识库文件列表点“重新抽取”，随后再“建立 / 重建索引”即可让旧文件用上 OCR 文本。

## 9. Docker 部署

- `Dockerfile` 多阶段构建：Node 18 + pnpm 构建 H5 → python:3.12-slim 运行 FastAPI 并托管 `dist/`（`server/main.py` 在 dist 存在时挂载 StaticFiles，API 路由优先）。
- 数据目录用环境变量 `MYOPENWEB_DATA_DIR=/data` 重定向到卷 `myopenweb-data`；首次启动可用 `PROVIDER_TYPE` / `PROVIDER_BASE_URL` / `PROVIDER_API_KEY` / `EMBEDDING_MODEL` 播种配置（之后以设置页保存的为准）。
- `docker-compose.yml`：默认连宿主机 Ollama（`host.docker.internal`，Linux 用 `extra_hosts: host-gateway`）；`--profile ollama` 可把 Ollama 一起编排（此时 `PROVIDER_BASE_URL=http://ollama:11434/v1`）。
- 用法见 README「Docker 一键部署」。OCR 与 rerank 属可选重依赖，不进主镜像。

## 10. 与主流框架对比（LangGraph 对照 demo）

`examples/langgraph-agent/` 用 LangGraph（StateGraph + ToolNode + 原生 function calling）复刻了主工程的「日志分析 + 知识检索」Agent，实测跑通（qwen2.5:3b）。这让"为什么不用 LangChain"从口头话术变成有代码支撑的结论：

| 维度 | 主工程手写循环 | LangGraph 版 |
|---|---|---|
| 控制流 | for 循环 + 显式分支 | StateGraph 声明节点与条件边 |
| 工具协议 | prompt 约定 JSON，自己解析容错 | bind_tools 走模型原生 function calling |
| 状态管理 | 手动维护 messages 与步数 | MessagesState 自动合并 |
| 可观测性 | 自建 agent_runs/agent_steps + SSE 事件 | graph.stream() 事件流 / LangSmith |
| 依赖成本 | 零新增 | ~40MB（langgraph + langchain 系） |
| 模型兼容 | 任意能输出 JSON 的模型 | 依赖模型端 tools 支持 |

**结论**：小规模、可控性优先时手写更划算（协议容错、观测字段全白盒）；出现多分支规划、并行工具、human-in-the-loop、checkpoint 恢复需求时应切 LangGraph，不再手写。主工程工具是纯函数，迁移只需 `@tool` 包装。完整说明见 `examples/langgraph-agent/README.md`。

## 11. 后续扩展预案（仅方案，未实现）

- **PostgreSQL + pgvector 迁移**：把 `chunks.embedding` 改为 `vector` 列，检索改为 SQL `ORDER BY embedding <=> :q LIMIT k`；`repositories` 层接口不变，替换实现即可，便于写"企业级"简历。
- **按文件增量索引**：当前为知识库整体重建，规模大后改为按文件维度增量更新 chunks 与 FTS。
- **Dify 作为可选编排 provider**：把 Dify 作为一种 provider 接入，复杂工作流交给 Dify，简单场景仍走自研链路。
