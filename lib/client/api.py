"""DeepSeekClient — session, profile, PoW, streaming chat."""
from __future__ import annotations

import concurrent.futures
import sys
import threading
from typing import Any, Iterator

from . import config as cfg
from . import http as httpx
from .errors import AuthError, UpstreamError, WAFChallenge
from .pow import PoWError, PoWSolver
from .sse import iter_events

_bg = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="dsweb")
_tls = threading.local()
_POW_ATTEMPTS = 5

_AUTH_CODES = {40003, 401, 40101, 40102}
_AUTH_MSGS = (
    "INVALID_TOKEN",
    "Missing Token",
    "Authorization Failed",
    "unauthorized",
    "invalid token",
)


def _raise_if_auth(data: Any, where: str) -> None:
    """DeepSeek often returns HTTP 200 with code=40003 on bad token."""
    if not isinstance(data, dict):
        return
    code = data.get("code")
    msg = str(data.get("msg") or "")
    bad = code in _AUTH_CODES or any(m.lower() in msg.lower() for m in _AUTH_MSGS)
    if bad:
        raise AuthError(
            f"auth invalid at {where}: {msg or code}. {AuthError.HINT}"
        )


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

    def _http(self):
        """Per-thread curl_cffi session (safe under parallel proxy requests)."""
        s = getattr(_tls, "http", None)
        if s is None:
            s = httpx.make_session()
            _tls.http = s
        return s

    # ── profile ───────────────────────────────────────────────
    def whoami(self) -> dict:
        """GET /users/current → biz_data (raises on auth/WAF failure)."""
        s = self._http()
        r = s.get(f"{cfg.API}/users/current", headers=httpx.headers(token=self.token))
        httpx.save_jar(s)
        if httpx.is_waf(r.status_code, r.headers):
            raise WAFChallenge("WAF challenge on whoami")
        if r.status_code != 200:
            raise UpstreamError(f"whoami HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        _raise_if_auth(data, "whoami")
        biz = (data.get("data") or {}).get("biz_data")
        if not isinstance(biz, dict):
            raise UpstreamError(f"whoami unexpected payload: {data}")
        return biz

    # ── session ───────────────────────────────────────────────
    def create_session(self) -> str:
        s = self._http()
        r = s.post(
            f"{cfg.API}/chat_session/create",
            headers=httpx.headers(token=self.token),
            json={"character_id": None},
        )
        httpx.save_jar(s)
        if httpx.is_waf(r.status_code, r.headers):
            raise WAFChallenge("WAF challenge creating session")
        data = r.json()
        _raise_if_auth(data, "create_session")
        biz = (data.get("data") or {}).get("biz_data") or {}
        sid = biz.get("id") or (biz.get("chat_session") or {}).get("id")
        if not sid:
            raise UpstreamError(f"create session: {data}")
        return sid

    def delete_session(self, session_id: str) -> None:
        if not session_id:
            return
        try:
            s = self._http()
            s.post(
                f"{cfg.API}/chat_session/delete",
                headers=httpx.headers(token=self.token),
                json={"chat_session_id": session_id},
            )
            httpx.save_jar(s)
        except Exception:
            pass
        if self._session_id == session_id:
            self._session_id = None

    def delete_session_async(self, session_id: str) -> None:
        """Fire-and-forget delete — don't block the SSE tail."""
        if session_id:
            _bg.submit(self.delete_session, session_id)

    def ensure_session(self) -> str:
        """Reuse sticky session id (when DS_SAVE_CHATS=true)."""
        if self._session_id:
            return self._session_id
        self._session_id = self.create_session()
        return self._session_id

    # ── pow ───────────────────────────────────────────────────
    def _fetch_pow_challenge(self, target: str = "/api/v0/chat/completion") -> dict:
        s = self._http()
        r = s.post(
            f"{cfg.API}/chat/create_pow_challenge",
            headers=httpx.headers(token=self.token),
            json={"target_path": target},
        )
        httpx.save_jar(s)
        if httpx.is_waf(r.status_code, r.headers):
            raise WAFChallenge("WAF challenge fetching pow")
        data = r.json()
        _raise_if_auth(data, "pow")
        ch = ((data.get("data") or {}).get("biz_data") or {}).get("challenge")
        if not ch:
            raise UpstreamError(f"no pow challenge returned: {data}")
        return ch

    def _pow_header(self, target: str = "/api/v0/chat/completion") -> str:
        """Fetch+solve PoW; retry soft solver misses, never retry auth."""
        last: Exception | None = None
        for attempt in range(1, _POW_ATTEMPTS + 1):
            try:
                ch = self._fetch_pow_challenge(target)
                return self._solver.prove(ch, target)
            except AuthError:
                raise
            except WAFChallenge:
                raise
            except PoWError as exc:
                last = exc
            except UpstreamError as exc:
                last = exc
                # Don't spin on non-solver upstream errors forever
                if "no pow challenge" not in str(exc).lower():
                    raise
            if attempt >= _POW_ATTEMPTS:
                break
            sys.stderr.write(f"  · pow retry {attempt}/{_POW_ATTEMPTS}: {last}\n")
            sys.stderr.flush()
        raise UpstreamError(
            f"pow failed after {_POW_ATTEMPTS} attempts: {last}"
        ) from last

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

    def _prepare(self, use_temp: bool, session_id: str | None, target: str):
        """Create session + PoW in parallel (saves one RTT)."""
        if session_id:
            return session_id, self._pow_header(target)

        sid_fut = _bg.submit(self.create_session if use_temp else self.ensure_session)
        pow_fut = _bg.submit(self._pow_header, target)
        # Prefer surfacing AuthError from either future
        sid_err = pow_err = None
        sid = pow_h = None
        try:
            sid = sid_fut.result()
        except Exception as exc:
            sid_err = exc
        try:
            pow_h = pow_fut.result()
        except Exception as exc:
            pow_err = exc
        err = sid_err or pow_err
        if isinstance(sid_err, AuthError):
            err = sid_err
        if isinstance(pow_err, AuthError):
            err = pow_err
        if err:
            if sid and use_temp:
                self.delete_session_async(sid)
            raise err
        return sid, pow_h

    # ── streaming ─────────────────────────────────────────────
    def stream(
        self,
        prompt: str,
        thinking: bool = False,
        search: bool = False,
        ref_file_ids=None,
        *,
        temp: bool | None = None,
        session_id: str | None = None,
    ) -> Iterator[tuple[str, str]]:
        """Yield (kind, text) where kind is 'content' or 'reasoning'.

        Default is throwaway upstream sessions (sidebar stays clean).
        Opt in to keep chats with DS_SAVE_CHATS=true or pass session_id.
        """
        use_temp = (not cfg.save_chats()) if temp is None else temp
        if session_id:
            use_temp = False

        last_err: Exception | None = None
        r = None
        sid = None
        for attempt in range(2):
            try:
                sid, pow_h = self._prepare(
                    use_temp, session_id, "/api/v0/chat/completion"
                )
            except AuthError:
                raise
            except Exception as exc:
                last_err = exc
                if attempt == 0 and isinstance(exc, (PoWError, UpstreamError)):
                    continue
                raise
            s = self._http()
            body = self._completion_body(
                sid, prompt, thinking, search, ref_file_ids, True
            )
            r = s.post(
                f"{cfg.API}/chat/completion",
                headers=httpx.headers(pow_h, token=self.token),
                json=body,
                stream=True,
            )
            if r.status_code == 200:
                # Auth errors sometimes arrive as first SSE/json line with 200
                httpx.save_jar(s)
                break
            txt = next(r.iter_lines(), b"")
            if use_temp:
                self.delete_session_async(sid)
                sid = None
            if httpx.is_waf(r.status_code, r.headers):
                raise WAFChallenge(f"WAF challenge on completion ({r.status_code})")
            # Try parse auth from error body
            try:
                _raise_if_auth(
                    __import__("json").loads(txt.decode() if isinstance(txt, bytes) else txt),
                    "completion",
                )
            except AuthError:
                raise
            except Exception:
                pass
            last_err = UpstreamError(f"completion {r.status_code}: {txt!r}")
            if attempt == 0 and r.status_code in (401, 403, 400, 429):
                sys.stderr.write(
                    f"  · completion retry after HTTP {r.status_code}\n"
                )
                sys.stderr.flush()
                continue
            raise last_err
        else:
            raise last_err or UpstreamError("completion failed")

        try:
            yield from iter_events(r.iter_lines())
        finally:
            if use_temp and sid:
                self.delete_session_async(sid)

    def chat(
        self,
        prompt: str,
        thinking: bool = False,
        search: bool = False,
        ref_file_ids=None,
        *,
        temp: bool | None = None,
        session_id: str | None = None,
    ) -> tuple[str, str]:
        content, reasoning = [], []
        for kind, text in self.stream(
            prompt,
            thinking=thinking,
            search=search,
            ref_file_ids=ref_file_ids,
            temp=temp,
            session_id=session_id,
        ):
            (reasoning if kind == "reasoning" else content).append(text)
        return "".join(content), "".join(reasoning)
