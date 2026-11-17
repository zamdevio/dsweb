"""curl_cffi session + shared headers."""
from __future__ import annotations

import os
import pathlib

from . import config as cfg

try:
    from curl_cffi import requests as creq
except ImportError:  # pragma: no cover
    raise SystemExit(
        "curl_cffi required: ./.venv/bin/pip install -r requirements.txt"
    ) from None


def is_waf(status: int, headers) -> bool:
    h = {k.lower(): v for k, v in dict(headers).items()}
    if status == 202 and h.get("x-amzn-waf-action"):
        return True
    if status in (403, 429) and h.get("cf-mitigated") == "challenge":
        return True
    return False


def make_session() -> "creq.Session":
    pathlib.Path(cfg.JAR).parent.mkdir(parents=True, exist_ok=True)
    kw = dict(impersonate=cfg.IMPERSONATE, timeout=cfg.TIMEOUT)
    if cfg.PROXY:
        kw["proxies"] = {"all": cfg.PROXY}
    s = creq.Session(**kw)
    try:
        if os.path.exists(cfg.JAR):
            s.cookies.load(cfg.JAR)
    except Exception:
        pass
    raw = cfg.cookie()
    if raw:
        for part in raw.split(";"):
            part = part.strip()
            if "=" not in part:
                continue
            name, value = part.split("=", 1)
            try:
                s.cookies.set(name.strip(), value.strip(), domain=".deepseek.com")
            except Exception:
                pass
    return s


def save_jar(session) -> None:
    try:
        session.cookies.save(cfg.JAR)
    except Exception:
        pass


def headers(pow_response: str | None = None, token: str | None = None) -> dict:
    h = {
        "User-Agent": cfg.UA,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        "Origin": cfg.BASE,
        "Referer": f"{cfg.BASE}/",
        "Sec-Ch-Ua": cfg.SEC_CH_UA,
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Client-Version": cfg.CLIENT_VERSION,
        "X-Client-Platform": "web",
        "X-Client-Locale": cfg.LOCALE,
        "X-Client-Timezone-Offset": cfg.TZ_OFFSET,
        "x-client-bundle-id": "com.deepseek.chat",
    }
    tok = token if token is not None else cfg.token()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    if pow_response:
        h["x-ds-pow-response"] = pow_response
    return h
