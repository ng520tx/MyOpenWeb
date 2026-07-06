"""Smoke test for the native function-calling agent protocol against a live
Ollama (qwen2.5). Verifies the model actually emits tool_calls through the
provider tools API and the loop completes with a real answer.

    MYOPENWEB_DATA_DIR=server/eval/.data ./.venv/bin/python -m server.eval.native_smoke
"""
from __future__ import annotations

import asyncio
import os

os.environ.setdefault("MYOPENWEB_DATA_DIR", "server/eval/.data")

from server.db import init_db  # noqa: E402
from server.schemas.config import ProviderConfig  # noqa: E402
from server.services.agent_runner import run_agent  # noqa: E402


async def main() -> int:
    init_db()
    config = ProviderConfig(agent_tool_protocol="native")
    model = os.environ.get("EVAL_CHAT_MODEL", "qwen2.5:3b")

    result = await run_agent(
        config,
        {
            "model": model,
            "messages": [{"role": "user", "content": "帮我算一下 (12 + 8) * 3 / 2 等于多少"}],
            "stream": False,
        },
    )
    tool_names = [call["name"] for call in result["agent"]["toolCalls"]]
    print(f"tool calls: {tool_names}")
    print(f"answer: {result['answer']}")
    assert "calculator" in tool_names, "native protocol did not trigger the calculator tool"
    assert "30" in result["answer"], f"unexpected answer: {result['answer']}"
    print("native protocol smoke: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
