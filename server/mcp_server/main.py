"""MyOpenWeb MCP Server：把企业知识库检索与研发/运维工具暴露为标准 MCP 工具。

任何支持 MCP 的客户端（Cursor / Claude Desktop / 自研 Agent）都能通过标准
协议直接调用 MyOpenWeb 的能力，而不需要走 HTTP API 适配：

- search_knowledge：完整复用主工程检索链路（混合检索 BM25+向量 RRF、可选 rerank）
- analyze_log / summarize_git_diff / summarize_ticket / generate_test_cases：
  复用 agent_tools 的纯函数实现（业务与编排解耦，一层包装即可挂到任何协议上）

运行（stdio transport，供 MCP 客户端以子进程方式拉起）：

    ./.venv/bin/python -m server.mcp_server.main

Cursor 配置示例（Windows 宿主 + WSL 后端场景，写入 ~/.cursor/mcp.json）：

    {
      "mcpServers": {
        "myopenweb": {
          "command": "wsl.exe",
          "args": ["bash", "-lc",
            "cd /mnt/d/ai_one/MyOpenWeb && ./.venv/bin/python -m server.mcp_server.main"]
        }
      }
    }
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from server.db import init_db
from server.repositories.configs import get_provider_config
from server.repositories.knowledge import list_knowledge
from server.services.agent_tools import run_tool
from server.services.rag import query_knowledge

mcp = FastMCP("myopenweb")


def _resolve_knowledge_id(name_or_id: str) -> str | None:
    """Accept either a knowledge base name or its id."""
    wanted = name_or_id.strip()
    if not wanted:
        return None
    for knowledge in list_knowledge():
        if knowledge.id == wanted or knowledge.name == wanted:
            return knowledge.id
    return None


@mcp.tool()
def list_knowledge_bases() -> list[dict[str, Any]]:
    """列出 MyOpenWeb 中的全部企业知识库（名称、描述、文件数、索引块数）。"""
    return [
        {
            "id": knowledge.id,
            "name": knowledge.name,
            "description": knowledge.description,
            "files": knowledge.file_count,
            "chunks": knowledge.chunk_count,
        }
        for knowledge in list_knowledge()
    ]


@mcp.tool()
async def search_knowledge(knowledge: str, query: str, top_k: int = 4) -> dict[str, Any]:
    """在指定企业知识库中检索资料片段（混合检索：BM25 + 向量 RRF 融合）。

    Args:
        knowledge: 知识库名称或 id（可先用 list_knowledge_bases 查看）
        query: 检索问题或关键词
        top_k: 返回片段数量，默认 4
    """
    knowledge_id = _resolve_knowledge_id(knowledge)
    if not knowledge_id:
        names = [item.name for item in list_knowledge()]
        return {"error": f"知识库 '{knowledge}' 不存在", "available": names}

    config = get_provider_config()
    chunks = await query_knowledge(
        config, config.embedding_model, knowledge_id, query, top_k=max(1, min(top_k, 10))
    )
    if not chunks:
        return {"results": [], "note": "知识库中没有找到相关内容"}
    return {
        "results": [
            {
                "filename": chunk["filename"],
                "score": round(chunk["score"], 4),
                "content": chunk["content"],
            }
            for chunk in chunks
        ]
    }


@mcp.tool()
def analyze_log(log: str) -> dict[str, Any]:
    """分析应用/运维日志：统计级别分布、抽取错误行与异常类型、定位首尾错误。"""
    return run_tool("analyze_log", {"log": log})


@mcp.tool()
def summarize_git_diff(diff: str) -> dict[str, Any]:
    """解析 git diff：统计变更文件与增删行数，输出变更摘要骨架。"""
    return run_tool("summarize_git_diff", {"diff": diff})


@mcp.tool()
def summarize_ticket(text: str) -> dict[str, Any]:
    """解析工单/需求文本：抽取工单号、相关人、链接与已填写字段。"""
    return run_tool("summarize_ticket", {"text": text})


@mcp.tool()
def generate_test_cases(requirement: str) -> dict[str, Any]:
    """根据接口/功能需求，给出测试用例覆盖维度与关键参数。"""
    return run_tool("generate_test_cases", {"requirement": requirement})


def main() -> None:
    init_db()
    mcp.run()


if __name__ == "__main__":
    main()
