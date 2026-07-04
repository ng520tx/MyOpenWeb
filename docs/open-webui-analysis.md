# Open WebUI 对照分析

分析对象：`D:\ai_top\open-webui`  
当前项目：`D:\ai_one\MyOpenWeb`

## 结论

Open WebUI 是完整平台，不是单纯聊天 App。  
它的核心复杂度集中在：

- 多 provider / 多模型路由
- 用户、权限、分享、分组
- 工具注册、工具权限、工具调用循环
- 文件、知识库、RAG、引用来源
- 记忆系统
- WebSocket 事件流
- Pipeline / Function 插件系统
- 多数据库迁移和大量配置项

MyOpenWeb 当前定位是个人版 AI App 骨架，因此不能整包照搬。  
合理路线是：抽取 Open WebUI 的架构原则，但只实现个人版最小闭环。

## Open WebUI 后端结构

关键目录：

```text
backend/open_webui/
├── main.py
├── config.py
├── functions.py
├── models/
├── routers/
├── retrieval/
├── tools/
├── utils/
└── socket/
```

### 1. 模型与聊天路由

相关文件：

- `backend/open_webui/utils/chat.py`
- `backend/open_webui/routers/openai.py`
- `backend/open_webui/routers/ollama.py`
- `backend/open_webui/functions.py`
- `backend/open_webui/utils/middleware.py`

Open WebUI 的聊天请求不是直接转发。  
它会先经过统一聊天入口，再按模型归属分发到 Ollama / OpenAI / Function / Pipeline 等不同路径。

核心思想：

```text
请求
→ 统一 chat completion 入口
→ 读取模型配置
→ 权限检查
→ pipeline/filter 处理
→ 工具 / RAG / memory 注入
→ 分发到真实 provider
→ 处理流式输出和事件
```

MyOpenWeb 当前已经实现了其中最小版：

```text
/api/chat/completions
→ ProviderConfig
→ Ollama / OpenAI Compatible
→ 统一 OpenAI SSE
```

下一步不需要照搬权限和 pipeline，应该补“可观测性”和“工具调用日志”。

## Tools / Agent 机制

相关文件：

- `backend/open_webui/utils/tools.py`
- `backend/open_webui/models/tools.py`
- `backend/open_webui/routers/tools.py`
- `backend/open_webui/tools/builtin.py`
- `backend/open_webui/utils/middleware.py`
- `backend/open_webui/config.py`

Open WebUI 有两类工具调用方式：

### 方式 A：Prompt 模拟函数调用

配置里有默认工具选择模板：

```text
Available Tools: {{TOOLS}}

Return only JSON:
{
  "tool_calls": [
    {"name": "toolName", "parameters": {"key": "value"}}
  ]
}
```

流程：

```text
用户问题
→ 用 task model 判断需要哪些工具
→ 解析 tool_calls
→ 执行工具
→ 把工具结果作为 sources/context 注入后续回答
```

这和 MyOpenWeb 当前 Agent v1 接近。  
区别是 Open WebUI 的格式是：

```json
{
  "tool_calls": [
    {
      "name": "calculator",
      "parameters": {
        "expression": "(12 + 8) * 3 / 2"
      }
    }
  ]
}
```

而 MyOpenWeb 当前格式是：

```json
{
  "action": "tool",
  "tool": "calculator",
  "input": {
    "expression": "(12 + 8) * 3 / 2"
  }
}
```

建议下一步把 MyOpenWeb 改成更接近 Open WebUI 的 `tool_calls` 数组格式。  
原因：后续天然支持一次调用多个工具，也更接近 OpenAI function calling 结构。

### 方式 B：Native Function Calling

Open WebUI 也支持模型原生 tool calls。  
在流式响应里，它会收集：

- `tool_calls`
- `function.name`
- `function.arguments`
- `tool_call_id`

然后执行工具，再把结果作为 `tool` / `function_call_output` 消息继续交给模型。

MyOpenWeb 暂时不应该做这一步。  
原因：

- Ollama 本地小模型对原生 tool calling 支持不稳定
- 当前阶段先把 prompt-tool-loop 做稳定更重要
- 后续再加 native tool calling 作为高级路径

## Tools 数据模型

Open WebUI 的 `tool` 表大致包含：

```text
tool
├── id
├── user_id
├── name
├── content
├── specs
├── meta
├── valves
├── created_at
└── updated_at
```

重点：

- `content` 存工具代码
- `specs` 存工具 schema
- `valves` 存工具配置
- 还有权限和 access grants

MyOpenWeb 当前不需要动态上传工具代码。  
下一步只需要：

```text
agent_tool
├── id
├── name
├── description
├── input_schema
├── enabled
└── created_at / updated_at
```

工具实现仍然放在后端白名单 Python 代码里，不允许用户上传任意代码。

## Agent 运行日志

Open WebUI 在流式过程中会向前端发送工具执行事件，并把工具结果合并到输出结构里。  
这给了用户一个关键能力：看见模型是否调用工具，以及工具执行结果是什么。

MyOpenWeb 当前缺这个能力。  
这是下一步最应该做的功能。

建议实现：

```text
agent_runs
├── id
├── conversation_id
├── message_id
├── model
├── user_input
├── final_answer
├── created_at
└── updated_at

agent_steps
├── id
├── run_id
├── step_index
├── type              # model_decision / tool_call / tool_result / final
├── name
├── input_json
├── output_json
├── ok
├── error
└── created_at
```

前端先不用做复杂调试面板。  
可以先在 assistant 消息下方显示：

```text
Agent: 调用了 calculator，结果 30
```

后续再做展开详情。

## Memory 机制

相关文件：

- `backend/open_webui/models/memories.py`
- `backend/open_webui/routers/memories.py`

Open WebUI 的 memory 分两层：

- 数据库存原始 memory 文本
- 向量库保存 embedding，用于相似度查询

结构很简单：

```text
memory
├── id
├── user_id
├── content
├── created_at
└── updated_at
```

MyOpenWeb 可以先做简化版：

```text
memories
├── id
├── content
├── category       # preference / profile / project / fact
├── enabled
├── created_at
└── updated_at
```

第一阶段不需要向量库。  
先把所有启用 memory 注入 system prompt 即可。数量多了再做 embedding/RAG。

## Files / Knowledge / RAG

相关文件：

- `backend/open_webui/models/files.py`
- `backend/open_webui/models/knowledge.py`
- `backend/open_webui/routers/retrieval.py`
- `backend/open_webui/retrieval/`

Open WebUI 把文件和知识库拆开：

```text
file
├── id
├── user_id
├── hash
├── filename
├── path
├── data
├── meta
├── created_at
└── updated_at

knowledge
├── id
├── user_id
├── name
├── description
├── meta
├── created_at
└── updated_at

knowledge_file
├── knowledge_id
└── file_id
```

这个拆法值得借鉴。  
MyOpenWeb 目前文件只是临时放在前端消息里，历史附件不可复用。

建议在 Agent 日志之后做：

```text
files
├── id
├── filename
├── path
├── mime_type
├── size
├── hash
├── text_content
├── meta_json
├── created_at
└── updated_at

chat_files
├── chat_id
├── message_id
└── file_id
```

RAG 先不要上向量库。  
第一阶段做“文件落盘 + 文本注入 + 可复用历史附件”。

## 不建议现在照搬的部分

暂时不要做：

- 用户系统
- 复杂权限
- Access Grants
- 动态上传 Python Tool
- MCP Tool Server
- OpenAPI Tool Server
- Pipeline / Filter 插件
- 多租户
- WebSocket 实时协作
- 大规模向量库
- PostgreSQL 迁移

这些是平台能力，不是当前个人版学习阶段的核心。

## MyOpenWeb 下一步建议

### 第 1 优先级：Agent 运行日志（已完成 v1）

原因：

- 你刚刚已经遇到工具 JSON 泄露问题
- 没有日志就不知道模型输出了什么、工具有没有执行、执行结果是什么
- Open WebUI 的工具机制大量依赖事件和中间态展示

已完成：

- 新增 `agent_runs` / `agent_steps` SQLite 表
- `run_agent()` 每一步写日志
- `/api/agent/runs/{id}` 查询详情
- 前端消息展示简要工具调用摘要

### 第 2 优先级：统一工具调用格式（已完成）

已把当前：

```json
{"action":"tool","tool":"calculator","input":{}}
```

调整为：

```json
{
  "tool_calls": [
    {
      "name": "calculator",
      "parameters": {}
    }
  ]
}
```

原因：

- 更接近 Open WebUI
- 更接近 OpenAI tool calls
- 后续支持多工具并行/串行更自然

### 第 3 优先级：Memory 简化版

已完成手动 memory：

- 新增 memory 管理接口
- 设置页或独立面板可添加/删除 memory
- Agent 请求自动注入启用 memory

不要一开始就做 embedding。

### 第 4 优先级：文件落盘

先做：

- 文件上传到后端
- SQLite 存 metadata
- 文件内容落盘
- 消息只保存 file_id

再做：

- 文本抽取
- 简单关键词检索
- 最后才做向量检索

## 推荐下一轮实际开发任务

下一轮建议直接做：**Agent 运行日志 v1**。

验收标准：

- 发送 “现在几点？”
- 后端记录一次 `agent_run`
- 记录模型第一次输出
- 记录调用 `get_current_time`
- 记录工具返回值
- 记录最终回答
- 前端 assistant 消息下显示：`Agent 调用 1 个工具：get_current_time`

这一步比继续加更多工具更重要。
