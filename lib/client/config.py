"""Env-backed config. Portable — no machine-specific hardcoded paths."""
from __future__ import annotations

import json
import os
import pathlib

# lib/client/config.py → repo root is parents[2], lib/ is parents[1]
LIB = pathlib.Path(__file__).resolve().parent.parent
ROOT = LIB.parent


def _xdg_config() -> pathlib.Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return pathlib.Path(base) / "dsweb"


def _xdg_data() -> pathlib.Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return pathlib.Path(base) / "dsweb"


CONFIG_DIR = pathlib.Path(
    os.environ.get("DS_CONFIG_DIR") or _xdg_config()
)
DATA_DIR = pathlib.Path(
    os.environ.get("DS_DATA_DIR") or _xdg_data()
)

BASE = os.environ.get("DS_BASE_URL", "https://chat.deepseek.com")
API = os.environ.get("DS_API", f"{BASE}/api/v0")
IMPERSONATE = os.environ.get("DS_IMPERSONATE", "chrome131")
PROXY = os.environ.get("DS_PROXY") or None
TIMEOUT = float(os.environ.get("DS_TIMEOUT", "600"))
WASM = os.environ.get("DS_WASM", str(LIB / "wasm" / "sha3_wasm_bg.wasm"))
JAR = os.environ.get("DS_COOKIE_JAR", str(DATA_DIR / "cookies.jar"))
AUTH_FILE = os.environ.get("DS_AUTH_FILE", str(CONFIG_DIR / "auth.json"))

CLIENT_VERSION = os.environ.get("DS_CLIENT_VERSION", "2.3.0")
LOCALE = os.environ.get("DS_CLIENT_LOCALE", "en_US")
TZ_OFFSET = os.environ.get("DS_CLIENT_TIMEZONE_OFFSET", "28800")
UA = os.environ.get(
    "DS_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
)
SEC_CH_UA = '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'


def _auth_file() -> dict:
    try:
        with open(AUTH_FILE, encoding="utf-8") as fh:
            return json.load(fh) or {}
    except Exception:
        return {}


def token() -> str:
    return os.environ.get("DS_TOKEN") or _auth_file().get("token") or ""


def cookie() -> str:
    return os.environ.get("DS_COOKIE") or _auth_file().get("cookie") or ""


TOKEN = token()
COOKIE = cookie()
