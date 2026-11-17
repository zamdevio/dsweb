"""Env-backed config. Portable — no machine-specific hardcoded paths.

Settings: process env > ~/.config/dsweb/config.json > defaults.
Secrets:  process env DS_TOKEN/DS_COOKIE > ~/.config/dsweb/auth.json.
Never reads secrets from .env / config.json.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

# lib/client/config.py → repo root is parents[2], lib/ is parents[1]
LIB = pathlib.Path(__file__).resolve().parent.parent
ROOT = LIB.parent

# Apply XDG config.json before reading settings (skips secrets).
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))
try:
    from xdg_config import apply_config_to_env  # type: ignore

    apply_config_to_env()
except Exception:
    pass


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
    # Explicit process env only — empty string in env must not block auth.json.
    env = os.environ.get("DS_TOKEN")
    if env:
        return env
    return _auth_file().get("token") or ""


def cookie() -> str:
    env = os.environ.get("DS_COOKIE")
    if env:
        return env
    return _auth_file().get("cookie") or ""


TOKEN = token()
COOKIE = cookie()


def _truthy(name: str, default: str) -> bool:
    v = (os.environ.get(name) or default).lower()
    return v in ("1", "true", "yes", "on")


def save_chats() -> bool:
    """Opt-in: keep upstream chat_session rows on chat.deepseek.com.

    Default is false (temp/throwaway) so the official sidebar stays clean.
    Set DS_SAVE_CHATS=true to persist. Legacy DS_TEMP_SESSIONS=false also
    enables saving.
    """
    if "DS_SAVE_CHATS" in os.environ:
        return _truthy("DS_SAVE_CHATS", "false")
    # legacy: DS_TEMP_SESSIONS=true → don't save
    return not _truthy("DS_TEMP_SESSIONS", "true")


def temp_sessions() -> bool:
    """Inverse of save_chats() — kept for older call sites."""
    return not save_chats()
