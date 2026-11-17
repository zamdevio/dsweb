"""Upstream client for chat.deepseek.com (unofficial)."""
from .api import DeepSeekClient
from .errors import UpstreamError, WAFChallenge

__all__ = ["DeepSeekClient", "UpstreamError", "WAFChallenge"]
