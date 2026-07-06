"""LangGraph 版「日志分析 + 知识检索」Agent —— 与主工程手写工具循环的对照实现。

主工程（server/services/agent_runner.py）用 ~200 行手写 while 循环 + prompt-based
JSON 协议实现同样的能力；这里用 LangGraph 的 StateGraph + ToolNode 复刻，
用于对比两种实现在状态管理、协议与可观测性上的差异（见本目录 README.md）。

运行（需要 Ollama 已拉取 qwen2.5:3b）：

    python -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/python agent.py "分析一下示例错误日志，最多的错误是什么？"
    .venv/bin/python agent.py "数据库连接池耗尽应该怎么处置？"
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

EXAMPLES_DIR = Path(__file__).resolve().parent.parent
MODEL = os.environ.get("DEMO_MODEL", "qwen2.5:3b")
# 显式走 IPv4：WSL 等环境下 localhost 可能解析为 ::1 导致连不上宿主机 Ollama。
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")


@tool
def analyze_log(filename: str = "error.log") -> str:
    """分析 examples 目录下的日志文件（默认 error.log），统计错误级别分布和出现最多的异常。"""
    # 小模型经常自由发挥文件名/路径，这里归一化并兜底到默认日志。
    path = EXAMPLES_DIR / Path(filename).name
    if not path.exists():
        path = EXAMPLES_DIR / "error.log"
    if not path.exists():
        return f"日志文件 {filename} 不存在"
    lines = path.read_text(encoding="utf-8").splitlines()
    levels = Counter()
    exceptions = Counter()
    for line in lines:
        for level in ("ERROR", "WARN", "INFO"):
            if f" {level} " in line or line.startswith(level):
                levels[level] += 1
        for match in re.findall(r"\b(\w+(?:Exception|Error))\b", line):
            exceptions[match] += 1
    top = ", ".join(f"{name}×{count}" for name, count in exceptions.most_common(3)) or "无异常堆栈"
    return f"共 {len(lines)} 行；级别分布 {dict(levels)}；出现最多的异常：{top}"


@tool
def search_knowledge(query: str) -> str:
    """在 examples 目录的运维手册/接口文档/FAQ 中检索与问题相关的章节。"""
    keywords = [word for word in re.split(r"[\s，。？?、]+", query) if len(word) >= 2]
    best_score, best_text = 0, ""
    for doc in EXAMPLES_DIR.glob("*.md"):
        # 按二/三级标题切成章节，保证命中的块带着完整的处置步骤而不只是标题行。
        sections = re.split(r"\n(?=#{2,3} )", doc.read_text(encoding="utf-8"))
        for section in sections:
            score = sum(section.count(keyword) for keyword in keywords)
            if score > best_score:
                best_score, best_text = score, f"[{doc.name}] {section.strip()}"
    return best_text[:800] if best_text else "知识库中没有找到相关内容"


TOOLS = [analyze_log, search_knowledge]


def build_graph():
    llm = ChatOllama(model=MODEL, base_url=OLLAMA_URL, temperature=0)
    llm_with_tools = llm.bind_tools(TOOLS)

    def agent_node(state: MessagesState):
        return {"messages": [llm_with_tools.invoke(state["messages"])]}

    builder = StateGraph(MessagesState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(TOOLS))
    builder.add_edge(START, "agent")
    # 模型输出含 tool_calls 时路由到 tools 节点，否则结束——
    # 等价于主工程手写循环里的 "decision.action == final" 分支。
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    return builder.compile()


def main() -> int:
    question = sys.argv[1] if len(sys.argv) > 1 else "分析一下示例错误日志，最多的错误是什么？"
    graph = build_graph()
    print(f"问题：{question}\n--- 事件流 ---")
    final_state = None
    for event in graph.stream({"messages": [HumanMessage(content=question)]}, stream_mode="values"):
        message = event["messages"][-1]
        kind = type(message).__name__
        if getattr(message, "tool_calls", None):
            calls = ", ".join(f"{c['name']}({c['args']})" for c in message.tool_calls)
            print(f"[{kind}] 请求调用工具：{calls}")
        else:
            preview = str(message.content).replace("\n", " ")[:150]
            print(f"[{kind}] {preview}")
        final_state = event
    print("--- 最终回答 ---")
    print(final_state["messages"][-1].content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
