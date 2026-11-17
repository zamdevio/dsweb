class UpstreamError(Exception):
    """Upstream API / transport failure."""


class WAFChallenge(UpstreamError):
    """AWS WAF / Cloudflare challenge blocked the request."""


class AuthError(UpstreamError):
    """Token rejected by chat.deepseek.com (expired / revoked / wrong)."""

    HINT = "re-auth: ./dsweb token   (paste fresh userToken from chat.deepseek.com)"
