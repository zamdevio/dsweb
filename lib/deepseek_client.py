"""Re-export. Prefer `from client import DeepSeekClient` with lib/ on sys.path."""
from __future__ import annotations

import pathlib
import sys

_LIB = pathlib.Path(__file__).resolve().parent
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from client import DeepSeekClient, UpstreamError, WAFChallenge  # noqa: E402,F401

__all__ = ["DeepSeekClient", "UpstreamError", "WAFChallenge"]
