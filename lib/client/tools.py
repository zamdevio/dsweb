"""Best-effort OpenAI tool-calls over the web chat upstream.

Web DeepSeek has no native tools API. We inject schemas into the prompt and
parse a strict XML/JSON envelope from the model reply.

DeepSeek models are also trained on native DSML. Real wire tags use the
*fullwidth* pipe U+FF5C (`｜`), e.g. `<｜DSML｜ invoke name="…">` — not ASCII
`|`. We normalize those, convert invokes → OpenAI tool_calls, and strip so
raw DSML never reaches clients like OpenCode.
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

# Fullwidth pipe used by DeepSeek DSML tokens (+ lookalikes terminals confuse).
_PIPE_CHARS = "\uff5c\u2502\u2503\u07c5|"  # ｜ │ ┃ ߅ |

_SYSTEM = """You have access to tools. When you need one, output ONLY one or more
tool call blocks — no prose before/after — using this exact format:

{open}
{{"name": "TOOL_NAME", "arguments": {{"arg": "value"}}}}
{close}

Rules:
- `arguments` must be a JSON object (not a string).
- If you can answer without tools, respond normally with plain text (no tool_call tags).
- Prefer tools when they are required to fulfill the user request accurately.
- Never use DSML, <|DSML|>, <｜DSML｜>, or any other tool markup — only {open}…{close}.
""".format(open=TOOL_OPEN, close=TOOL_CLOSE)


def normalize_dsml(text: str) -> str:
    """Canonicalize DeepSeek DSML tags to ASCII `<|DSML|…>` form.

    Handles fullwidth `｜`, spaced UI leaks, and V4 / V4.1 tag spacing:
      <｜DSML｜ calls> / <｜DSML｜invoke> / <|DSML| tool_calls>
    """
    if not text or "DSML" not in text:
        return text
    out = text
    for ch in _PIPE_CHARS:
        if ch != "|":
            out = out.replace(ch, "|")
    # < | DSML | |  or  <|DSML|  →  <|DSML|
    out = re.sub(r"<\s*\|\s*DSML\s*\|\s*\|?\s*", "<|DSML|", out, flags=re.I)
    out = re.sub(r"</\s*\|\s*DSML\s*\|\s*\|?\s*", "</|DSML|", out, flags=re.I)
    return out


# After normalize_dsml: <|DSML|invoke …> or <|DSML| invoke …>
_DSML_INVOKE_RE = re.compile(
    r"<\|DSML\|\s*invoke\b([^>]*)>(.*?)</\|DSML\|\s*invoke\s*>",
    re.DOTALL | re.IGNORECASE,
)
_DSML_PARAM_RE = re.compile(
    r"<\|DSML\|\s*parameter\b([^>]*)>(.*?)</\|DSML\|\s*parameter\s*>",
    re.DOTALL | re.IGNORECASE,
)
# Entire tool-call region (calls / tool_calls wrapper) — for hard strip.
_DSML_BLOCK_RE = re.compile(
    r"<\|DSML\|\s*(?:calls|tool_calls)\s*>.*?</\|DSML\|\s*(?:calls|tool_calls)\s*>",
    re.DOTALL | re.IGNORECASE,
)
_DSML_TAG_RE = re.compile(r"</?\|DSML\|\s*[^>]*>", re.IGNORECASE)


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


def _attr(attrs: str, key: str) -> str:
    m = re.search(rf'\b{re.escape(key)}\s*=\s*"([^"]*)"', attrs or "", re.I)
    if m:
        return m.group(1)
    m = re.search(rf"\b{re.escape(key)}\s*=\s*'([^']*)'", attrs or "", re.I)
    return m.group(1) if m else ""


def _openai_call(name: str, args: Any) -> dict:
    if isinstance(args, str):
        args_str = args
    else:
        args_str = json.dumps(args if args is not None else {}, ensure_ascii=False)
    return {
        "id": f"call_{uuid.uuid4().hex[:24]}",
        "type": "function",
        "function": {"name": name, "arguments": args_str},
    }


def _parse_jsonish(raw: str) -> Any:
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        raw2 = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I).strip()
        try:
            return json.loads(raw2)
        except Exception:
            return raw


def _parse_our_tool_calls(text: str) -> list[dict]:
    if not text or TOOL_OPEN not in text:
        return []
    calls: list[dict] = []
    for match in _TOOL_RE.finditer(text):
        obj = _parse_jsonish(match.group(1))
        if not isinstance(obj, dict):
            continue
        name = obj.get("name") or obj.get("tool") or ""
        args = obj.get("arguments", obj.get("parameters", obj.get("args", {})))
        if not name:
            continue
        calls.append(_openai_call(name, args))
    return calls


def _parse_dsml_tool_calls(text: str) -> list[dict]:
    """Convert DeepSeek DSML invoke blocks → OpenAI tool_calls."""
    if not text or "DSML" not in text:
        return []
    norm = normalize_dsml(text)
    calls: list[dict] = []
    for inv in _DSML_INVOKE_RE.finditer(norm):
        name = _attr(inv.group(1), "name")
        if not name:
            continue
        args: dict[str, Any] = {}
        body = inv.group(2) or ""
        for pm in _DSML_PARAM_RE.finditer(body):
            pname = _attr(pm.group(1), "name") or "arguments"
            raw = (pm.group(2) or "").strip()
            is_string = _attr(pm.group(1), "string").lower()
            if is_string in ("true", "1", "yes"):
                args[pname] = raw
            else:
                parsed = _parse_jsonish(raw)
                if pname == "arguments" and isinstance(parsed, dict):
                    args.update(parsed)
                else:
                    args[pname] = parsed
        if list(args.keys()) == ["arguments"] and isinstance(args["arguments"], dict):
            args = args["arguments"]
        calls.append(_openai_call(name, args))
    return calls


def parse_tool_calls(text: str) -> list[dict]:
    """Extract OpenAI-shaped tool_calls from model text. Empty if none."""
    calls = _parse_our_tool_calls(text)
    if calls:
        return calls
    return _parse_dsml_tool_calls(text)


def contains_tool_markup(text: str) -> bool:
    if not text:
        return False
    if TOOL_OPEN in text or "DSML" in text:
        return True
    return any(ch in text for ch in "\uff5c") and "DSML" in text.replace("\uff5c", "|")


def strip_tool_blocks(text: str) -> str:
    """Remove tool_call + DSML envelopes; leftover is normal assistant content.

    Guarantees: if input had DSML, output will not contain the string 'DSML'
    unless something pathological remains outside tags (then we hard-cut).
    """
    if not text:
        return ""
    cleaned = _TOOL_RE.sub("", text)
    if "DSML" in cleaned or any(ch in cleaned for ch in _PIPE_CHARS if ch != "|"):
        norm = normalize_dsml(cleaned)
        # Drop whole calls/tool_calls blocks first (includes invoke bodies).
        norm = _DSML_BLOCK_RE.sub("", norm)
        # Orphan invoke blocks (no wrapper).
        norm = _DSML_INVOKE_RE.sub("", norm)
        # Any leftover DSML tags.
        norm = _DSML_TAG_RE.sub("", norm)
        cleaned = norm
    cleaned = cleaned.strip()
    # Nuclear: never leak DSML wire format to clients.
    if "DSML" in cleaned:
        idx = cleaned.upper().find("DSML")
        # cut from nearest `<` before DSML, else from DSML itself
        lt = cleaned.rfind("<", 0, idx)
        cleaned = cleaned[: lt if lt >= 0 else idx].rstrip()
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
