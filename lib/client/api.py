"""DeepSeekClient — session, profile, PoW, streaming chat."""
from __future__ import annotations

from typing import Iterator

from . import config as cfg
from . import http as httpx
from .errors import UpstreamError, WAFChallenge
from .pow import PoWSolver
from .sse import iter_events


class DeepSeekClient:
    def __init__(self, token: str | None = None):
        self._token_override = token
        self._solver = PoWSolver()
        self._session_id: str | None = None

    @property
    def token(self) -> str:
        if self._token_override is not None:
            return self._token_override
        return cfg.token()

    # ── profile ───────────────────────────────────────────────
    def whoami(self) -> dict:
        """GET /users/current → biz_data (raises on auth/WAF failure)."""
        s = httpx.make_session()
        r = s.get(f"{cfg.API}/users/current", headers=httpx.headers(token=self.token))
        httpx.save_jar(s)
        if httpx.is_waf(r.status_code, r.headers):
            raise WAFChallenge("WAF challenge on whoami")
        if r.status_code != 200:
            raise UpstreamError(f"whoami HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        msg = data.get("msg") or ""
        if msg in ("Missing Token", "INVALID_TOKEN"):
            raise UpstreamError(f"auth invalid: {msg}")
        biz = (data.get("data") or {}).get("biz_data")
        if not isinstance(biz, dict):
            raise UpstreamError(f"whoami unexpected payload: {data}")
        return biz

    # ── session ───────────────────────────────────────────────
    def ensure_session(self) -> str:
        if self._session_id:
            return self._session_id
        s = httpx.make_session()
        r = s.post(
            f"{cfg.API}/chat_session/create",
            headers=httpx.headers(token=self.token),
            json={"character_id": None},
        )
        httpx.save_jar(s)
        if httpx.is_waf(r.status_code, r.headers):
            raise WAFChallenge("WAF challenge creating session")
        data = r.json()
        biz = (data.get("data") or {}).get("biz_data") or {}
        sid = biz.get("id") or (biz.get("chat_session") or {}).get("id")
        if not sid:
            raise UpstreamError(f"create session: {data}")
        self._session_id = sid
        return sid

    # ── pow ───────────────────────────────────────────────────
    def _pow_header(self, target: str = "/api/v0/chat/completion") -> str:
        s = httpx.make_session()
        r = s.post(
            f"{cfg.API}/chat/create_pow_challenge",
            headers=httpx.headers(token=self.token),
            json={"target_path": target},
        )
        httpx.save_jar(s)
        if httpx.is_waf(r.status_code, r.headers):
            raise WAFChallenge("WAF challenge fetching pow")
        ch = ((r.json().get("data") or {}).get("biz_data") or {}).get("challenge")
        if not ch:
            raise UpstreamError("no pow challenge returned")
        return self._solver.prove(ch, target)

    @staticmethod
    def _completion_body(session_id, prompt, thinking, search, ref_ids, stream):
        return {
            "chat_session_id": session_id,
            "parent_message_id": None,
            "model_type": None,
            "prompt": prompt,
            "ref_file_ids": ref_ids or [],
            "stream": stream,
            "thinking_enabled": thinking,
            "search_enabled": search,
            "preempt": False,
        }

    # ── streaming ─────────────────────────────────────────────
    def stream(
        self,
        prompt: str,
        thinking: bool = False,
        search: bool = False,
        ref_file_ids=None,
    ) -> Iterator[tuple[str, str]]:
        """Yield (kind, text) where kind is 'content' or 'reasoning'."""
        sid = self.ensure_session()
        pow_h = self._pow_header()
        s = httpx.make_session()
        body = self._completion_body(sid, prompt, thinking, search, ref_file_ids, True)
        r = s.post(
            f"{cfg.API}/chat/completion",
            headers=httpx.headers(pow_h, token=self.token),
            json=body,
            stream=True,
        )
        if r.status_code != 200:
            txt = next(r.iter_lines(), b"")
            if httpx.is_waf(r.status_code, r.headers):
                raise WAFChallenge(f"WAF challenge on completion ({r.status_code})")
            raise UpstreamError(f"completion {r.status_code}: {txt!r}")
        httpx.save_jar(s)
        yield from iter_events(r.iter_lines())

    def chat(
        self,
        prompt: str,
        thinking: bool = False,
        search: bool = False,
        ref_file_ids=None,
    ) -> tuple[str, str]:
        content, reasoning = [], []
        for kind, text in self.stream(
            prompt, thinking=thinking, search=search, ref_file_ids=ref_file_ids
        ):
            (reasoning if kind == "reasoning" else content).append(text)
        return "".join(content), "".join(reasoning)
