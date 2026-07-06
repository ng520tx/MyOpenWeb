# LangGraph 对照 Demo：与主工程手写 Agent 循环的对比

主工程的 Agent（`server/services/agent_runner.py`）是 **~200 行手写工具循环 + prompt-based JSON 协议**。
本目录用 **LangGraph（StateGraph + ToolNode + 原生 function calling）** 复刻同样的「日志分析 + 知识检索」能力，
目的不是替换主工程实现，而是回答一个高频问题：**"为什么不用 LangChain/LangGraph？"——用过、对比过、有结论。**

## 运行

```bash
cd examples/langgraph-agent
python -m venv .venv
.venv/bin/pip install -r requirements.txt

# 需要 Ollama 已拉取 qwen2.5:3b；WSL 内访问宿主机时用网关 IP：
# OLLAMA_HOST=http://$(ip route | awk '/default/ {print $3; exit}'):11434
.venv/bin/python agent.py "分析一下示例错误日志，最多的错误是什么？"
.venv/bin/python agent.py "数据库连接池耗尽应该怎么处置？"
```

实测输出（qwen2.5:3b，事件流展示图的每一步）：

```text
问题：数据库连接池耗尽应该怎么处置？
--- 事件流 ---
[HumanMessage] 数据库连接池耗尽应该怎么处置？
[AIMessage] 请求调用工具：search_knowledge({'query': '数据库连接池耗尽 处置'})
[ToolMessage] [ops-manual.md] ### 6.1 数据库连接池耗尽 ...
[AIMessage] 根据运维手册的指导……
--- 最终回答 ---
1. 执行 SHOW PROCESSLIST 检查 MySQL 是否存在慢查询堆积
2. 检查连接池配置：resource-api 的 HikariCP 最大连接数默认为 50
3. 如存在慢 SQL，先 kill 慢查询恢复业务，再走 SQL 优化流程
4. 临时扩容连接池需评估 MySQL max_connections（当前为 500）
```

## 两种实现对照

| 维度 | 主工程手写循环 | LangGraph 版 |
|---|---|---|
| 控制流 | `for` 循环 + 显式分支（final / tool_calls / 超步数） | `StateGraph` 声明节点与条件边，框架驱动 |
| 工具协议 | prompt 约定 JSON（`{"tool_calls":[...]}`），自己解析与容错 | `bind_tools` 走模型原生 function calling |
| 状态管理 | 手动维护 `messages` 列表与步数 | `MessagesState` 自动合并消息 |
| 可观测性 | 自建 `agent_runs`/`agent_steps` 表 + SSE 步骤事件 | `graph.stream()` 事件流（生态有 LangSmith） |
| 依赖成本 | 0 额外依赖（httpx + FastAPI 已有） | langgraph + langchain-core + langchain-ollama（约 40MB） |
| 协议兼容性 | 任意能输出 JSON 的模型（含不支持 function calling 的小模型） | 依赖模型端 tools 支持（qwen2.5 支持，部分小模型不支持） |
| 代码量（本场景） | ~200 行（含日志落库、知识库融合、拒答策略） | ~110 行 |

## 结论（面试版）

- **小规模、可控性优先**：手写循环让协议、容错（小模型输出 `{"action":"calculator",...}` 这类脏格式的归一化）、观测字段全部白盒可调，没有版本地狱。
- **流程复杂化后**：当出现多分支规划、并行工具、人工审批插入（human-in-the-loop）、需要 checkpoint 恢复时，LangGraph 的图模型与持久化状态明显更划算，不应该继续手写。
- **迁移成本可控**：主工程的工具都是纯函数（`agent_tools.py`），换到 LangGraph 只需要用 `@tool` 包装——这正是"业务与编排解耦"的收益。
