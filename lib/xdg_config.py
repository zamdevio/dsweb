"""Load ~/.config/dsweb/config.json into the process environment.

Precedence (highest wins):
  1. process env already set
  2. config.json
  3. caller defaults

Secrets (token/cookie) are NEVER read from config.json or .env — only
auth.json / explicit DS_TOKEN process env.
"""
from __future__ import annotations

import json
import os
import pathlib
from typing import Any

_SECRET_KEYS = frozenset({
    "DS_TOKEN", "DS_COOKIE", "DS_PASSWORD", "DS_EMAIL",
})

_DEFAULTS: dict[str, Any] = {
    "DS_HOST": "127.0.0.1",
    "DS_PORT": "8787",
    "DS_API_KEY": "sk-dsweb-change-me",
    "DS_MODEL": "deepseek-chat",
    "DS_SAVE_CHATS": "false",
    "DS_DEFAULT_THINKING": "false",
    "DS_DEFAULT_SEARCH": "false",
    "DS_TIMEOUT": "600",
    "DS_ALLOW_UNAUTHENTICATED": "false",
}


def config_path() -> pathlib.Path:
    base = os.environ.get("DS_CONFIG_DIR")
    if not base:
        xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        base = str(pathlib.Path(xdg) / "dsweb")
    return pathlib.Path(base) / "config.json"


def auth_path() -> pathlib.Path:
    override = os.environ.get("DS_AUTH_FILE")
    if override:
        return pathlib.Path(override)
    return config_path().parent / "auth.json"


def load_config_file() -> dict[str, Any]:
    path = config_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def apply_config_to_env(data: dict[str, Any] | None = None) -> None:
    """Fill os.environ from config.json for keys not already set. Skips secrets."""
    if data is None:
        data = load_config_file()
    for key, val in data.items():
        if not isinstance(key, str) or not key.startswith("DS_"):
            continue
        if key in _SECRET_KEYS:
            continue
        if key in os.environ and os.environ[key] != "":
            continue
        if val is None:
            continue
        if isinstance(val, bool):
            os.environ[key] = "true" if val else "false"
        else:
            os.environ[key] = str(val)


def _seed_from_dotenv() -> dict[str, Any]:
    """Pull non-secret DS_* from repo .env once when creating config.json."""
    root = pathlib.Path(__file__).resolve().parent.parent
    env_path = root / ".env"
    out: dict[str, Any] = dict(_DEFAULTS)
    if not env_path.is_file():
        return out
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip("\"'")
            if not k.startswith("DS_") or k in _SECRET_KEYS or not v:
                continue
            out[k] = v
    except Exception:
        pass
    return out


def ensure_config_file() -> pathlib.Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_text(
            json.dumps(_seed_from_dotenv(), indent=2) + "\n",
            encoding="utf-8",
        )
        try:
            os.chmod(path, 0o644)
        except Exception:
            pass
    return path


def get(key: str, default: Any = None) -> Any:
    if key in os.environ and os.environ[key] != "":
        return os.environ[key]
    data = load_config_file()
    if key in data:
        return data[key]
    return _DEFAULTS.get(key, default)


def set_key(key: str, value: Any) -> pathlib.Path:
    if key in _SECRET_KEYS:
        raise ValueError(f"{key} belongs in auth.json — use: ./dsweb token")
    if not key.startswith("DS_"):
        raise ValueError("keys must start with DS_")
    path = ensure_config_file()
    data = load_config_file()
    data[key] = value
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def unset_key(key: str) -> pathlib.Path:
    path = ensure_config_file()
    data = load_config_file()
    data.pop(key, None)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path
