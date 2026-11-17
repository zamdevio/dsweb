"""Parse DeepSeek chat SSE into (kind, text) pairs.

kind is 'content' or 'reasoning'.
"""
from __future__ import annotations

import json
from typing import Iterator


def _finished(obj: dict) -> bool:
    p = obj.get("p") or ""
    v = obj.get("v")
    if v == "FINISHED" and "status" in p:
        return True
    if obj.get("o") == "BATCH" and isinstance(v, list):
        for item in v:
            if (
                isinstance(item, dict)
                and item.get("p") == "quasi_status"
                and item.get("v") == "FINISHED"
            ):
                return True
    if isinstance(v, dict) and (v.get("response") or {}).get("status") == "FINISHED":
        return True
    choices = obj.get("choices")
    if isinstance(choices, list) and choices:
        if choices[0].get("finish_reason") == "stop":
            return True
    return False


def iter_events(lines) -> Iterator[tuple[str, str]]:
    """Yield ('content'|'reasoning', text) from SSE byte/str lines."""
    mode = "RESPONSE"
    for raw in lines:
        if not raw:
            continue
        line = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
        if line.startswith("data:"):
            line = line[5:].lstrip()
        line = line.strip()
        if not line or line in ("[DONE]", "null"):
            continue
        try:
            data = json.loads(line)
        except Exception:
            continue

        v = data.get("v")
        o = data.get("o")
        p = data.get("p") or ""
        out: list[tuple[str, str]] = []

        if isinstance(v, dict) and isinstance((v.get("response") or {}).get("fragments"), list):
            for frag in v["response"]["fragments"]:
                ftype = frag.get("type") or "RESPONSE"
                mode = ftype
                text = frag.get("content") or ""
                if text:
                    out.append(("reasoning" if ftype == "THINK" else "content", text))
        elif p == "response/fragments" and isinstance(v, list):
            for frag in v:
                ftype = frag.get("type") or "RESPONSE"
                if ftype == "RESPONSE" and mode != "RESPONSE":
                    text = frag.get("content") or ""
                    if text:
                        out.append(("content", text))
                mode = ftype
        elif o == "APPEND" and p.endswith("/content") and isinstance(v, str):
            out.append(("reasoning" if mode == "THINK" else "content", v))
        elif isinstance(v, str) and not p and o is None and v != "FINISHED":
            out.append(("reasoning" if mode == "THINK" else "content", v))
        elif data.get("choices"):
            d = data["choices"][0].get("delta") or {}
            if d.get("reasoning_content"):
                out.append(("reasoning", d["reasoning_content"]))
            if d.get("content"):
                out.append(("content", d["content"]))

        yield from out
        if _finished(data):
            break
