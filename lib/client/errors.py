class UpstreamError(Exception):
    """Upstream API / transport failure."""


class WAFChallenge(UpstreamError):
    """AWS WAF / Cloudflare challenge blocked the request."""
