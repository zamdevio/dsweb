"""Best-effort OpenAI tool-calls over the web chat upstream.

Web DeepSeek has no native tools API. We inject schemas into the prompt and
parse a strict XML/JSON envelope from the model reply.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

TOOL_OPEN = "<tool_call>"
TOOL_CLOSE = "</tool_call>"

_TOOL_RE = re.compile(
    re.escape(TOOL_OPEN) + r"\s*(.*?)\s*" + re.escape(TOOL_CLOSE),
    re.DOTALL | re.IGNORECASE,
)

_SYSTEM = """You have access to tools. When you need one, output ONLY one or more
tool call blocks — no prose before/after — using this exact format:

{open}
{{"name": "TOOL_NAME", "arguments": {{"arg": "value"}}}}
{close}

Rules:
- `arguments` must be a JSON object (not a string).
- If you can answer without tools, respond normally with plain text (no tool_call tags).
- Prefer tools when they are required to fulfill the user request accurately.
""".format(open=TOOL_OPEN, close=TOOL_CLOSE)


def _fn_name(tool: dict) -> str:
    if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
        return tool["function"].get("name") or ""
    return tool.get("name") or ""


def _fn_desc(tool: dict) -> str:
    if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
        return tool["function"].get("description") or ""
    return tool.get("description") or ""


def _fn_params(tool: dict) -> Any:
    if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
        return tool["function"].get("parameters") or {}
    return tool.get("parameters") or tool.get("input_schema") or {}


def render_tools_prompt(tools: list[dict], tool_choice: Any = None) -> str:
    """Schema block appended to the upstream prompt."""
    if not tools:
        return ""
    lines = [_SYSTEM.strip(), "", "Available tools (JSON schemas):"]
    for t in tools:
        schema = {
            "name": _fn_name(t),
            "description": _fn_desc(t),
            "parameters": _fn_params(t),
        }
        lines.append(json.dumps(schema, ensure_ascii=False))
    if tool_choice and tool_choice not in ("auto", "none", None):
        if isinstance(tool_choice, dict):
            forced = (
                (tool_choice.get("function") or {}).get("name")
                or tool_choice.get("name")
            )
            if forced:
                lines.append(f"\nYou MUST call the tool named `{forced}`.")
        elif tool_choice == "required":
            lines.append("\nYou MUST call at least one tool.")
    elif tool_choice == "none":
        return ""  # caller should omit tools entirely
    return "\n".join(lines)


def parse_tool_calls(text: str) -> list[dict]:
    """Extract OpenAI-shaped tool_calls from model text. Empty if none."""
    if not text or TOOL_OPEN not in text:
        return []
    calls: list[dict] = []
    for match in _TOOL_RE.finditer(text):
        raw = match.group(1).strip()
        try:
            obj = json.loads(raw)
        except Exception:
            # tolerate markdown fences inside the block
            raw2 = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I).strip()
            try:
                obj = json.loads(raw2)
            except Exception:
                continue
        name = obj.get("name") or obj.get("tool") or ""
        args = obj.get("arguments", obj.get("parameters", obj.get("args", {})))
        if isinstance(args, str):
            args_str = args
        else:
            args_str = json.dumps(args if args is not None else {}, ensure_ascii=False)
        if not name:
            continue
        calls.append({
            "id": f"call_{uuid.uuid4().hex[:24]}",
            "type": "function",
            "function": {"name": name, "arguments": args_str},
        })
    return calls


def strip_tool_blocks(text: str) -> str:
    """Remove tool_call envelopes; leftover is normal assistant content."""
    if not text:
        return ""
    cleaned = _TOOL_RE.sub("", text).strip()
    return cleaned


def messages_to_prompt(messages: list[dict], tools: list[dict] | None = None,
                       tool_choice: Any = None) -> str:
    """Flatten OpenAI-style messages (+ optional tools) into one web prompt."""
    parts: list[str] = []
    sys_parts: list[str] = []

    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):
            content = "".join(
                c.get("text", "") for c in content if isinstance(c, dict)
            )
        content = content or ""

        if role == "system":
            sys_parts.append(content)
        elif role == "assistant":
            tcs = m.get("tool_calls")
            if tcs:
                blocks = []
                for tc in tcs:
                    fn = tc.get("function") or {}
                    payload = {
                        "name": fn.get("name"),
                        "arguments": _safe_json(fn.get("arguments")),
                    }
                    blocks.append(
                        f"{TOOL_OPEN}\n{json.dumps(payload, ensure_ascii=False)}\n{TOOL_CLOSE}"
                    )
                extra = content.strip()
                parts.append(
                    "Assistant: " + ("\n".join(blocks) + (("\n" + extra) if extra else ""))
                )
            else:
                parts.append(f"Assistant: {content}")
        elif role == "tool":
            name = m.get("name") or m.get("tool_call_id") or "tool"
            parts.append(f"Tool result ({name}): {content}")
        else:
            parts.append(f"User: {content}")

    chunks: list[str] = []
    if sys_parts:
        chunks.append("\n".join(sys_parts))
    tool_block = ""
    if tools and tool_choice != "none":
        tool_block = render_tools_prompt(tools, tool_choice)
        if tool_block:
            chunks.append(tool_block)
    if parts:
        chunks.append("\n".join(parts))
    return "\n\n".join(c for c in chunks if c).strip()


def _safe_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value if value is not None else {}
