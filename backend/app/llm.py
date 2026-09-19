"""Shared LLM helper for agent nodes.

Every LLM-backed node follows the same convention: call the configured provider when an API
key is set, and fall back to its deterministic stub when it isn't — or when the live call
fails for any reason. Centralizing the forced-tool-use call keeps that failure handling in
one place: a node never crashes the pipeline because of a network error or a bad key; it
just degrades to its stub.

Provider: OpenAI (chat completions, forced function-calling). Every calling node writes its
tool schema and vision content blocks in Anthropic's shape (input_schema / {"type": "image",
"source": {...}}) for historical reasons — this module is the single place that translates
them to OpenAI's wire format, so nodes stay provider-agnostic and swapping providers again
later only means editing this file.
"""

import json
import logging

from app.config import settings

MODEL = "gpt-4o"

log = logging.getLogger(__name__)


def llm_enabled() -> bool:
    return bool(settings.openai_api_key)


def _convert_content(content):
    """A plain string passes through untouched. A content-block list may contain Anthropic's
    vision shape ({"type": "image", "source": {"media_type", "data"}}) — translate those to
    OpenAI's {"type": "image_url", "image_url": {"url": "data:...;base64,..."}} and pass any
    other block (e.g. {"type": "text", ...}) through as-is.
    """
    if isinstance(content, str):
        return content

    blocks = []
    for block in content:
        if block.get("type") == "image":
            source = block["source"]
            data_url = f"data:{source['media_type']};base64,{source['data']}"
            blocks.append({"type": "image_url", "image_url": {"url": data_url}})
        else:
            blocks.append(block)
    return blocks


def _convert_tool(tool: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool["input_schema"],
        },
    }


async def forced_tool_call(
    system: str, content, tool: dict, max_tokens: int = 2000
) -> dict | None:
    """Run a single forced-function-call OpenAI request and return the call's argument
    payload as a dict.

    `content` is a user-message content value — a plain string or a content-block list (e.g.
    image + text for vision), written in Anthropic's shape and translated here. Returns None
    on any failure so the caller can fall back to its deterministic stub.
    """
    if not llm_enabled():
        return None
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=MODEL,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": _convert_content(content)},
            ],
            tools=[_convert_tool(tool)],
            tool_choice={"type": "function", "function": {"name": tool["name"]}},
        )
        call = response.choices[0].message.tool_calls[0]
        return json.loads(call.function.arguments)
    except Exception:
        log.exception("LLM call failed; node falls back to its stub")
    return None
