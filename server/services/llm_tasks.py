"""Async LLM enhancement tasks: conversation titles and follow-up suggestions.

参考 open-webui 的 tasks 思路（标题/追问/标签都是独立的小请求），但 prompt 自研、
零框架依赖。两个共同设计点：

- 都是"锦上添花"：由前端在回答完成后异步调用，失败静默（标题保持截断文本、
  追问不显示），绝不阻塞或破坏聊天主链路
- 都用 temperature 低值 + 小 max_tokens 控制成本与稳定性
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from server.schemas.config import ProviderConfig
from server.services.providers import create_chat_completion_text

logger = logging.getLogger(__name__)

MAX_TITLE_CHARS = 20
MAX_FOLLOW_UPS = 3
MAX_CONTEXT_CHARS = 800

TITLE_INSTRUCTION = """根据用户问题（以及助手回答的开头）为这段对话生成一个标题：
- 不超过 16 个字，概括对话主题
- 使用与用户问题相同的语言
- 只输出标题本身：不要引号、句号、书名号，不要任何解释"""

FOLLOW_UPS_INSTRUCTION = """你是追问建议生成器。站在用户视角，根据对话生成 3 条用户接下来最可能提出的追问：
- 每条不超过 20 个字，具体、可直接发送
- 不要与已经回答过的内容重复，要有信息增量
- 使用与对话相同的语言
- 只输出一个 JSON 字符串数组，不要任何解释
- 数组元素就是追问本身，禁止加"追问一："、"1."之类的编号前缀
例：["批量接口的限流是多少？","限流阈值可以调整吗？","触发限流后多久恢复？"]"""


def _clip(text: str, limit: int = MAX_CONTEXT_CHARS) -> str:
    text = (text or "").strip()
    return text[:limit]


async def generate_title(
    config: ProviderConfig, model: str, user_text: str, assistant_text: str = ""
) -> str | None:
    prompt = f"用户问题：{_clip(user_text)}"
    if assistant_text.strip():
        prompt += f"\n\n助手回答（开头）：{_clip(assistant_text, 300)}"

    try:
        raw = await create_chat_completion_text(
            config,
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "system_prompt": TITLE_INSTRUCTION,
                "temperature": 0.1,
                "max_tokens": 64,
                "stream": False,
            },
        )
    except Exception as exc:  # noqa: BLE001 - enhancement task, fail silently
        logger.warning("title generation failed: %s", exc)
        return None

    title = raw.strip().splitlines()[0].strip() if raw.strip() else ""
    title = title.strip("\"'“”《》「」").rstrip("。.！!？?").strip()
    if not title:
        return None
    return title[:MAX_TITLE_CHARS]


def _parse_follow_ups(raw: str) -> list[str]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    candidates: Any = None
    try:
        candidates = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", text, flags=re.S)
        if match:
            try:
                candidates = json.loads(match.group(0))
            except json.JSONDecodeError:
                candidates = None
    if not isinstance(candidates, list):
        return []
    cleaned: list[str] = []
    for item in candidates:
        if not isinstance(item, (str, int, float)):
            continue
        text_item = str(item).strip().strip("\"'“”")
        # 小模型常无视指令加编号前缀（"追问一："、"1. "），统一剥掉。
        text_item = re.sub(r"^(?:追问[一二三四五12345]?|建议|问题)[\s:：.、]*", "", text_item)
        text_item = re.sub(r"^\d+[.、)]\s*", "", text_item).strip()
        if text_item:
            cleaned.append(text_item)
    return cleaned[:MAX_FOLLOW_UPS]


async def generate_follow_ups(
    config: ProviderConfig, model: str, messages: list[dict[str, Any]]
) -> list[str]:
    lines: list[str] = []
    for message in messages[-4:]:
        role = "用户" if message.get("role") == "user" else "助手"
        content = message.get("content", "")
        if isinstance(content, str) and content.strip():
            lines.append(f"{role}：{_clip(content, 400)}")
    if not lines:
        return []

    try:
        raw = await create_chat_completion_text(
            config,
            {
                "model": model,
                "messages": [{"role": "user", "content": "对话记录：\n" + "\n".join(lines)}],
                "system_prompt": FOLLOW_UPS_INSTRUCTION,
                "temperature": 0.4,
                "max_tokens": 256,
                "stream": False,
            },
        )
    except Exception as exc:  # noqa: BLE001 - enhancement task, fail silently
        logger.warning("follow-up generation failed: %s", exc)
        return []

    return _parse_follow_ups(raw)
