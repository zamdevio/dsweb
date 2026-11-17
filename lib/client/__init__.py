"""Upstream client for chat.deepseek.com (unofficial)."""
from .api import DeepSeekClient
from .errors import AuthError, UpstreamError, WAFChallenge

__all__ = ["DeepSeekClient", "AuthError", "UpstreamError", "WAFChallenge"]
