#!/usr/bin/env python3
"""
proxy.py - OpenAI-compatible + Anthropic-compatible local proxy for
chat.deepseek.com (unofficial).

Endpoints:
  GET  /health
  GET  /v1/models
  POST /v1/chat/completions        (OpenAI, streaming + non-streaming + tools)
  POST /v1/messages                (Anthropic Messages, basic)

Auth: Authorization: Bearer <DS_API_KEY> (or x-api-key).

Thinking → reasoning_content / Anthropic thinking blocks.
Tools → prompt-injected schemas + <tool_call> parse (web upstream has no native tools).
"""
from __future__ import annotations

import os
import sys
import json
import time
import uuid
import pathlib
import threading

LIB = pathlib.Path(__file__).resolve().parent
ROOT = LIB.parent
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from client import DeepSeekClient, UpstreamError  # noqa: E402
from client.tools import (  # noqa: E402
    messages_to_prompt,
    parse_tool_calls,
    strip_tool_blocks,
)

try:
    from fastapi import FastAPI, Request, Header, HTTPException
    from fastapi.responses import JSONResponse, StreamingResponse
    import uvicorn
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(
        f"missing deps: {exc}\nrun: ./.venv/bin/pip install -r requirements.txt\n"
    )
    raise

DS_API_KEY = os.environ.get("DS_API_KEY", "sk-dsweb-change-me")
ALLOW_UNAUTH = os.environ.get("DS_ALLOW_UNAUTHENTICATED", "false").lower() in (
    "1", "true", "yes", "on",
)
DEFAULT_MODEL = os.environ.get("DS_MODEL", "deepseek-chat")
DEFAULT_SYSTEM = os.environ.get("DS_SYSTEM_PROMPT", "")
HOST = os.environ.get("DS_HOST", "127.0.0.1")
PORT = int(os.environ.get("DS_PORT", "8787"))
DS_COLOR = os.environ.get("DS_COLOR", "auto").lower()

_client = DeepSeekClient()
app = FastAPI(title="dsweb proxy", version="0.2.0")

# ── request stats ─────────────────────────────────────────────
_stats_lock = threading.Lock()
_stats = {
    "total": 0,
    "ok": 0,
    "err": 0,
    "chat": 0,
    "messages": 0,
    "other": 0,
}


def _color_enabled() -> bool:
    if DS_COLOR in ("never", "0", "false", "no", "off"):
        return False
    if DS_COLOR in ("always", "1", "true", "yes", "on"):
        return True
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stderr.isatty()


def _c(code: str, text: str) -> str:
    if not _color_enabled():
        return text
    return f"\033[{code}m{text}\033[0m"


def _log_req(n: int, method: str, path: str, status: int, ms: float, extra: str = ""):
    if status >= 500:
        st = _c("31;1", str(status))
    elif status >= 400:
        st = _c("33;1", str(status))
    else:
        st = _c("32;1", str(status))
    tag = _c("36;1", f"#{n}")
    path_s = _c("1", path)
    ms_s = _c("2", f"{ms:.0f}ms")
    bit = f"  {_c('2', extra)}" if extra else ""
    sys.stderr.write(f"  {tag}  {method:4} {path_s}  {st}  {ms_s}{bit}\n")
    sys.stderr.flush()


@app.middleware("http")
async def _count_requests(request: Request, call_next):
    path = request.url.path
    # Don't spam health checks from cloudflared / doctor
    quiet = path in ("/health", "/favicon.ico")
    t0 = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    except Exception:
        status = 500
        raise
    finally:
        ms = (time.perf_counter() - t0) * 1000
        with _stats_lock:
            _stats["total"] += 1
            n = _stats["total"]
            if status >= 400:
                _stats["err"] += 1
            else:
                _stats["ok"] += 1
            if path.startswith("/v1/chat/completions"):
                _stats["chat"] += 1
                kind = "chat"
            elif path.startswith("/v1/messages"):
                _stats["messages"] += 1
                kind = "anthropic"
            else:
                _stats["other"] += 1
                kind = ""
        if not quiet:
            extra = kind
            _log_req(n, request.method, path, status, ms, extra)


def _check_auth(authorization: str | None, x_api_key: str | None):
    if ALLOW_UNAUTH and not (authorization or x_api_key):
        return
    provided = None
    if authorization and authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()
    elif x_api_key:
        provided = x_api_key.strip()
    if provided != DS_API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")


def _new_id(prefix: str = "chatcmpl") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:24]}"


def _map_model(model: str | None) -> dict:
    m = (model or DEFAULT_MODEL).lower()
    thinking = "reason" in m or "think" in m
    return {"model": DEFAULT_MODEL, "thinking": thinking}


def _build_prompt(messages: list[dict], tools, tool_choice) -> str:
    prompt = messages_to_prompt(messages, tools=tools, tool_choice=tool_choice)
    if DEFAULT_SYSTEM:
        prompt = f"{DEFAULT_SYSTEM}\n\n{prompt}".strip()
    return prompt


def _chunk(obj: dict) -> bytes:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode()


def _sse_headers():
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


@app.get("/health")
def health():
    with _stats_lock:
        stats = dict(_stats)
    return {
        "ok": True,
        "upstream": os.environ.get("DS_BASE_URL", ""),
        "auth_mode": "token+cookie",
        "tools": "prompt-emulated",
        "requests": stats,
    }


@app.get("/v1/models")
def list_models(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
):
    _check_auth(authorization, x_api_key)
    now = int(time.time())
    ids = ["deepseek-chat", "deepseek-reasoner"]
    return {
        "object": "list",
        "data": [
            {"id": i, "object": "model", "created": now, "owned_by": "deepseek"}
            for i in ids
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
):
    _check_auth(authorization, x_api_key)
    body = await request.json()

    messages = body.get("messages") or []
    if not messages:
        raise HTTPException(400, "messages required")

    tools = body.get("tools") or []
    tool_choice = body.get("tool_choice", "auto")
    if tool_choice == "none":
        tools = []

    prompt = _build_prompt(messages, tools, tool_choice)
    stream = bool(body.get("stream"))
    mapped = _map_model(body.get("model"))
    thinking = bool(body.get("thinking", mapped["thinking"]))
    search = bool(body.get("search", body.get("web_search", False)))

    created = int(time.time())
    cmpl_id = _new_id()
    model_name = body.get("model") or DEFAULT_MODEL

    if not stream:
        try:
            content, reasoning = _client.chat(
                prompt, thinking=thinking, search=search
            )
        except UpstreamError as exc:
            raise HTTPException(502, str(exc)) from exc

        tool_calls = parse_tool_calls(content) if tools else []
        if tool_calls:
            msg = {
                "role": "assistant",
                "content": strip_tool_blocks(content) or None,
                "tool_calls": tool_calls,
            }
            finish = "tool_calls"
        else:
            msg = {"role": "assistant", "content": content}
            finish = "stop"
        if reasoning:
            msg["reasoning_content"] = reasoning

        return JSONResponse({
            "id": cmpl_id,
            "object": "chat.completion",
            "created": created,
            "model": model_name,
            "choices": [{
                "index": 0,
                "message": msg,
                "finish_reason": finish,
            }],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        })

    # Streaming: buffer content when tools are enabled so we can emit tool_calls.
    def event_stream():
        yield _chunk({
            "id": cmpl_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "choices": [{
                "index": 0,
                "delta": {"role": "assistant"},
                "finish_reason": None,
            }],
        })
        buf_content: list[str] = []
        try:
            for kind, text in _client.stream(
                prompt, thinking=thinking, search=search
            ):
                if kind == "reasoning":
                    yield _chunk({
                        "id": cmpl_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {"reasoning_content": text},
                            "finish_reason": None,
                        }],
                    })
                    continue
                if tools:
                    buf_content.append(text)
                    continue
                yield _chunk({
                    "id": cmpl_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model_name,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": text},
                        "finish_reason": None,
                    }],
                })
        except UpstreamError as exc:
            yield _chunk({
                "id": cmpl_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model_name,
                "choices": [{
                    "index": 0,
                    "delta": {"content": f"\n[error: {exc}]"},
                    "finish_reason": "stop",
                }],
            })
            yield b"data: [DONE]\n\n"
            return

        finish = "stop"
        if tools:
            full = "".join(buf_content)
            tool_calls = parse_tool_calls(full)
            if tool_calls:
                finish = "tool_calls"
                # OpenAI streaming tool_calls: role already sent; emit tool_call deltas
                for i, tc in enumerate(tool_calls):
                    yield _chunk({
                        "id": cmpl_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {
                                "tool_calls": [{
                                    "index": i,
                                    "id": tc["id"],
                                    "type": "function",
                                    "function": {
                                        "name": tc["function"]["name"],
                                        "arguments": tc["function"]["arguments"],
                                    },
                                }]
                            },
                            "finish_reason": None,
                        }],
                    })
                leftover = strip_tool_blocks(full)
                if leftover:
                    yield _chunk({
                        "id": cmpl_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": leftover},
                            "finish_reason": None,
                        }],
                    })
            else:
                if full:
                    yield _chunk({
                        "id": cmpl_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": full},
                            "finish_reason": None,
                        }],
                    })

        yield _chunk({
            "id": cmpl_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": finish,
            }],
        })
        yield b"data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=_sse_headers(),
    )


@app.post("/v1/messages")
async def anthropic_messages(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
):
    """Minimal Anthropic Messages shim."""
    _check_auth(authorization, x_api_key)
    body = await request.json()

    msgs = body.get("messages") or []
    system = body.get("system") or ""
    openai_msgs = (
        [{"role": "system", "content": system}] if system else []
    ) + msgs
    prompt = _build_prompt(openai_msgs, tools=None, tool_choice=None)
    stream = bool(body.get("stream"))
    model_name = body.get("model") or "claude-3-5-sonnet"
    mapped = _map_model(model_name)
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"

    if not stream:
        content, reasoning = _client.chat(prompt, thinking=mapped["thinking"])
        blocks = []
        if reasoning:
            blocks.append({"type": "thinking", "thinking": reasoning})
        blocks.append({"type": "text", "text": content})
        return JSONResponse({
            "id": msg_id,
            "type": "message",
            "role": "assistant",
            "model": model_name,
            "content": blocks,
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        })

    def events():
        def ev(d):
            return f"event: {d['type']}\ndata: {json.dumps(d)}\n\n".encode()

        yield ev({
            "type": "message_start",
            "message": {
                "id": msg_id,
                "type": "message",
                "role": "assistant",
                "model": model_name,
                "content": [],
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        })
        yield ev({
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "text", "text": ""},
        })
        for kind, text in _client.stream(prompt, thinking=mapped["thinking"]):
            if kind != "content":
                continue
            yield ev({
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": text},
            })
        yield ev({"type": "content_block_stop", "index": 0})
        yield ev({
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"output_tokens": 0},
        })
        yield ev({"type": "message_stop"})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers=_sse_headers(),
    )


def _banner():
    mint = "38;5;49;1"
    dim = "2"
    base = f"http://{HOST}:{PORT}"
    lines = [
        _c(mint, "dsweb serve"),
        _c(dim, "─" * 44),
        f"  {_c(dim, 'listen')}   {base}/v1",
        f"  {_c(dim, 'health')}   {base}/health",
        f"  {_c(dim, 'model')}    {DEFAULT_MODEL}",
        f"  {_c(dim, 'tools')}    prompt-emulated",
        f"  {_c(dim, 'key')}      {'set' if DS_API_KEY else 'missing'}",
        _c(dim, "─" * 44),
        f"  {_c(dim, 'requests log below · Ctrl-C to stop')}",
        "",
    ]
    sys.stderr.write("\n" + "\n".join(lines) + "\n")
    sys.stderr.flush()


def main():
    _banner()
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
