from __future__ import annotations

import ast
import operator
import re
from datetime import datetime
from typing import Any


class ToolError(ValueError):
    pass


# Knowledge retrieval is async and needs request context (provider config +
# selected knowledge base), so it is executed inside the agent runner rather
# than the synchronous run_tool dispatch. This is just its public spec.
KNOWLEDGE_TOOL_NAME = "search_knowledge"


def knowledge_search_tool() -> dict[str, Any]:
    return {
        "name": KNOWLEDGE_TOOL_NAME,
        "description": "在用户选定的企业知识库中检索与问题相关的资料片段。当需要依据知识库 / 文档 / 手册回答时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索关键词或问题，通常就是用户的问题原文"},
                "top_k": {"type": "integer", "description": "返回片段数量，默认 4"},
            },
            "required": ["query"],
        },
    }


_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def list_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "get_current_time",
            "description": "获取当前服务器时间，适合回答今天、现在、当前时间等问题。",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "calculator",
            "description": "执行安全的四则运算表达式，支持 + - * / // % ** 和括号。",
            "input_schema": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "例如：'(12 + 8) * 3 / 2'",
                    }
                },
                "required": ["expression"],
            },
        },
        {
            "name": "analyze_log",
            "description": "分析应用/运维日志：统计日志级别、抽取错误行与异常类型、定位首尾错误，便于排查故障。当用户粘贴日志、报错堆栈、异常信息时使用。",
            "input_schema": {
                "type": "object",
                "properties": {
                    "log": {"type": "string", "description": "需要分析的原始日志文本"}
                },
                "required": ["log"],
            },
        },
        {
            "name": "summarize_git_diff",
            "description": "解析 git diff/unified diff：统计变更文件、各文件新增/删除行数、总变更量，便于生成代码变更摘要与风险评估。当用户粘贴 diff 或代码变更时使用。",
            "input_schema": {
                "type": "object",
                "properties": {
                    "diff": {"type": "string", "description": "git diff 文本"}
                },
                "required": ["diff"],
            },
        },
        {
            "name": "summarize_ticket",
            "description": "解析工单/需求文本：抽取工单号、@相关人、链接、已填写字段，并给出结构化摘要骨架，便于快速理解工单。当用户粘贴工单、需求、问题描述时使用。",
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "工单或需求原文"}
                },
                "required": ["text"],
            },
        },
        {
            "name": "generate_test_cases",
            "description": "根据接口或功能需求，给出测试用例的覆盖维度与已识别的关键参数，便于生成结构化测试用例。当用户要求写测试用例时使用。",
            "input_schema": {
                "type": "object",
                "properties": {
                    "requirement": {"type": "string", "description": "接口或功能需求描述"}
                },
                "required": ["requirement"],
            },
        },
    ]


def run_tool(name: str, tool_input: dict[str, Any] | None = None) -> dict[str, Any]:
    tool_input = tool_input or {}
    if name == "get_current_time":
        now = datetime.now().astimezone()
        return {
            "timezone": now.tzname(),
            "iso": now.isoformat(timespec="seconds"),
            "readable": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        }

    if name == "calculator":
        expression = str(tool_input.get("expression", "")).strip()
        return {
            "expression": expression,
            "result": _safe_calculate(expression),
        }

    if name == "analyze_log":
        return _analyze_log(str(tool_input.get("log", "")))

    if name == "summarize_git_diff":
        return _summarize_git_diff(str(tool_input.get("diff", "")))

    if name == "summarize_ticket":
        return _summarize_ticket(str(tool_input.get("text", "")))

    if name == "generate_test_cases":
        return _generate_test_cases(str(tool_input.get("requirement", "")))

    raise ToolError(f"Unknown tool: {name}")


def _dedupe(items: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
        if len(result) >= limit:
            break
    return result


_LEVEL_PATTERN = re.compile(r"\b(FATAL|ERROR|WARN(?:ING)?|INFO|DEBUG|TRACE)\b")
_EXCEPTION_PATTERN = re.compile(r"\b([A-Za-z_][\w.]*(?:Error|Exception|Throwable))\b")


def _analyze_log(log: str) -> dict[str, Any]:
    log = log.strip()
    if not log:
        raise ToolError("日志内容为空")

    lines = log.splitlines()
    level_counts: dict[str, int] = {}
    error_lines: list[str] = []
    exceptions: list[str] = []

    for line in lines:
        match = _LEVEL_PATTERN.search(line)
        if match:
            level = match.group(1).upper()
            if level == "WARNING":
                level = "WARN"
            level_counts[level] = level_counts.get(level, 0) + 1
            if level in ("ERROR", "FATAL"):
                error_lines.append(line.strip())
        exceptions.extend(_EXCEPTION_PATTERN.findall(line))

    return {
        "total_lines": len(lines),
        "level_counts": level_counts,
        "error_count": len(error_lines),
        "errors_sample": [line[:300] for line in error_lines[:10]],
        "exception_types": _dedupe(exceptions, 10),
        "first_error": error_lines[0][:300] if error_lines else None,
        "last_error": error_lines[-1][:300] if error_lines else None,
        "hint": "请基于以上结构化信息，分析最可能的根因，并给出排查步骤和修复建议。",
    }


_DIFF_HEADER = re.compile(r"^diff --git a/(?:.+?) b/(.+)$")


def _summarize_git_diff(diff: str) -> dict[str, Any]:
    diff = diff.strip()
    if not diff:
        raise ToolError("diff 内容为空")

    files: list[dict[str, Any]] = []
    total_added = 0
    total_removed = 0

    for line in diff.splitlines():
        header = _DIFF_HEADER.match(line)
        if header:
            files.append({"file": header.group(1), "added": 0, "removed": 0})
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            total_added += 1
            if files:
                files[-1]["added"] += 1
        elif line.startswith("-"):
            total_removed += 1
            if files:
                files[-1]["removed"] += 1

    return {
        "files_changed": len(files),
        "total_added": total_added,
        "total_removed": total_removed,
        "files": files[:20],
        "hint": "请基于以上变更统计，生成一段变更摘要，并指出潜在风险点和需要重点 review 的文件。",
    }


_TICKET_ID = re.compile(r"(?:[A-Z][A-Z0-9]+-\d+|#\d+)")
_MENTION = re.compile(r"@([\w\u4e00-\u9fa5]+)")
_URL = re.compile(r"https?://\S+")
_FIELD_LABEL = re.compile(r"^\s*([\u4e00-\u9fa5A-Za-z][\u4e00-\u9fa5A-Za-z ]{1,11})\s*[:：]", re.MULTILINE)


def _summarize_ticket(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ToolError("工单内容为空")

    return {
        "char_count": len(text),
        "ticket_ids": _dedupe(_TICKET_ID.findall(text), 10),
        "mentions": _dedupe(_MENTION.findall(text), 10),
        "urls": _dedupe(_URL.findall(text), 10),
        "detected_fields": _dedupe(_FIELD_LABEL.findall(text), 15),
        "scaffold": ["背景", "目标", "影响范围", "处理方案", "待办事项", "风险"],
        "hint": "请按 scaffold 的结构对工单进行简洁摘要，缺失的部分标注“工单未提供”。",
    }


def _generate_test_cases(requirement: str) -> dict[str, Any]:
    requirement = requirement.strip()
    if not requirement:
        raise ToolError("需求内容为空")

    return {
        "char_count": len(requirement),
        "detected_numbers": _dedupe(re.findall(r"\d+", requirement), 20),
        "categories": ["正常流程", "边界值", "异常/错误输入", "权限与安全", "并发与性能", "兼容性"],
        "hint": "请为每个 category 给出具体测试用例，每条包含：用例标题、前置条件、操作步骤、预期结果。",
    }


def _safe_calculate(expression: str) -> int | float:
    if not expression:
        raise ToolError("Calculator expression is empty")
    if len(expression) > 120:
        raise ToolError("Calculator expression is too long")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ToolError("Calculator expression syntax is invalid") from exc

    return _eval_node(tree.body)


def _eval_node(node: ast.AST) -> int | float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value

    if isinstance(node, ast.BinOp):
        operator_func = _BINARY_OPERATORS.get(type(node.op))
        if operator_func is None:
            raise ToolError("Calculator operator is not allowed")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        return operator_func(left, right)

    if isinstance(node, ast.UnaryOp):
        operator_func = _UNARY_OPERATORS.get(type(node.op))
        if operator_func is None:
            raise ToolError("Calculator unary operator is not allowed")
        return operator_func(_eval_node(node.operand))

    raise ToolError("Calculator expression contains unsupported syntax")
