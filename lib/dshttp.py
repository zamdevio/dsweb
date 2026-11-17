#!/usr/bin/env python3
"""
dshttp.py - WAF-aware HTTP bridge for chat.deepseek.com.

Uses curl_cffi with a real Chrome TLS/JA3 fingerprint (plain curl trips
AWS WAF -> 202 x-amzn-waf-action=challenge with an empty body).

CLI:
  dshttp.py request METHOD PATH [JSON_BODY]
      reads DS_TOKEN / DS_COOKIE / DS_POW_RESPONSE / DS_BASE_URL from env.
      stdout = response body, then a final line: <status>\t<bodylen>
      exit 1 on WAF challenge (after retries) or transport error.

  dshttp.py warm
      primes the session (hits the app shell) so WAF cookies land in the jar.

The jar is kept in a file so successive bash invocations share it.
"""
import os
import sys
import json
import time
import pathlib

BASE = os.environ.get("DS_BASE_URL", "https://chat.deepseek.com")
API_PREFIX = os.environ.get("DS_API_PREFIX", "/api/v0")
IMPERSONATE = os.environ.get("DS_IMPERSONATE", "chrome131")
PROXY = os.environ.get("DS_PROXY") or None
JAR = os.environ.get("DS_COOKIE_JAR") or os.path.expanduser(
    "~/.local/share/dsweb/cookies.jar"
)

CLIENT_VERSION = os.environ.get("DS_CLIENT_VERSION", "2.3.0")
LOCALE = os.environ.get("DS_CLIENT_LOCALE", "en_US")
TZ_OFFSET = os.environ.get("DS_CLIENT_TIMEZONE_OFFSET", "28800")
UA = os.environ.get(
    "DS_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
)
SEC_CH_UA = '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'


def _session():
    from curl_cffi import requests as creq

    pathlib.Path(JAR).parent.mkdir(parents=True, exist_ok=True)
    kwargs = dict(impersonate=IMPERSONATE, timeout=120, verify=True)
    if PROXY:
        kwargs["proxies"] = {"all": PROXY}
    sess = creq.Session(**kwargs)
    # persistent jar across process invocations
    try:
        if os.path.exists(JAR):
            sess.cookies.load(JAR)
    except Exception:
        pass
    return sess


def _save_jar(sess):
    try:
        sess.cookies.save(JAR)
    except Exception:
        pass


def _seed_user_cookie(sess):
    raw = os.environ.get("DS_COOKIE") or ""
    if not raw:
        return
    for part in raw.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        try:
            sess.cookies.set(name.strip(), value.strip(), domain=".deepseek.com")
        except Exception:
            pass


def _headers(extra=None):
    h = {
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        "Origin": BASE,
        "Referer": f"{BASE}/",
        "Sec-Ch-Ua": SEC_CH_UA,
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Client-Version": CLIENT_VERSION,
        "X-Client-Platform": "web",
        "X-Client-Locale": LOCALE,
        "X-Client-Timezone-Offset": TZ_OFFSET,
        "x-client-bundle-id": "com.deepseek.chat",
    }
    tok = os.environ.get("DS_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    pow_h = os.environ.get("DS_POW_RESPONSE")
    if pow_h:
        h["x-ds-pow-response"] = pow_h
    if extra:
        h.update(extra)
    return h


def _is_waf(status, headers):
    if status == 202 and headers.get("x-amzn-waf-action"):
        return "aws-waf"
    if status in (403, 429) and headers.get("cf-mitigated") == "challenge":
        return "cloudflare"
    return None


def warm():
    sess = _session()
    try:
        sess.get(f"{BASE}/", headers={"User-Agent": UA})
    except Exception:
        pass
    _save_jar(sess)
    return 0


def request(method, path, body=None, retries=2):
    sess = _session()
    _seed_user_cookie(sess)
    if path.startswith("http"):
        url = path
    elif path.startswith("/api/"):
        url = f"{BASE}{path}"
    else:
        url = f"{BASE}{API_PREFIX}{path}"
    data = body.encode() if isinstance(body, str) else body

    out_path = os.environ.get("DS_HTTP_OUT")
    last = None
    for attempt in range(retries + 1):
        try:
            resp = sess.request(
                method,
                url,
                headers=_headers(),
                data=data,
            )
        except Exception as exc:  # transport
            last = f"transport error: {exc}"
            time.sleep(0.4)
            continue

        status = resp.status_code
        kind = _is_waf(status, {k.lower(): v for k, v in resp.headers.items()})
        text = resp.text
        _save_jar(sess)

        if kind and attempt < retries:
            try:
                sess.get(f"{BASE}/", headers={"User-Agent": UA})
            except Exception:
                pass
            time.sleep(0.6)
            last = f"{kind} challenge on attempt {attempt+1}"
            continue

        if out_path:
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(text)
        else:
            sys.stdout.write(text)
        # status + body length on stderr, parseable
        sys.stderr.write(f"__DS_STATUS__ {status} {len(text)}\n")
        return 0

    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write("")
    sys.stderr.write("__DS_STATUS__ 0 0\n")
    sys.stderr.write(f"__DS_ERROR__ {last}\n")
    return 1


def main(argv):
    if len(argv) >= 2 and argv[1] == "warm":
        return warm()
    if len(argv) >= 3 and argv[1] == "request":
        method = argv[2]
        path = argv[3] if len(argv) > 3 else "/"
        body = argv[4] if len(argv) > 4 else None
        return request(method, path, body)
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
