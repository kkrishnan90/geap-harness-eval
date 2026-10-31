"""Public read-only vs IAP-protected admin.

Behind the load balancer, /admin/* and /api/admin/* route to an IAP-enabled backend; IAP adds a signed JWT
(x-goog-iap-jwt-assertion). The public backend could forward a forged header, so the JWT is verified against
Google's IAP keys, the admin backend's audience and an email allowlist — never trusted by presence alone.
Locally (GEAP_PUBLIC_READONLY unset) everything is allowed.
"""

from __future__ import annotations

import os
from functools import lru_cache

from fastapi import HTTPException, Request

IAP_CERTS = "https://www.gstatic.com/iap/verify/public_key"


def readonly_mode() -> bool:
    return os.environ.get("GEAP_PUBLIC_READONLY", "0") == "1"


@lru_cache(maxsize=1)
def _admins() -> set[str]:
    return {e.strip().lower() for e in os.environ.get("GEAP_ADMIN_EMAILS", "").split(",") if e.strip()}


def iap_identity(request: Request) -> str | None:
    """Verified IAP email, or None."""
    token = request.headers.get("x-goog-iap-jwt-assertion")
    audience = os.environ.get("GEAP_IAP_AUDIENCE")
    if not token or not audience:
        return None
    try:
        import google.auth.transport.requests
        from google.oauth2 import id_token

        claims = id_token.verify_token(token, google.auth.transport.requests.Request(), audience=audience,
                                       certs_url=IAP_CERTS)
    except Exception:  # noqa: BLE001 - invalid signature / audience / expiry
        return None
    if claims.get("iss") != "https://cloud.google.com/iap":
        return None
    email = (claims.get("email") or "").lower()
    return email if email in _admins() else None


def whoami(request: Request) -> dict:
    if not readonly_mode():
        return {"admin": True, "email": None, "readonly": False}
    email = iap_identity(request)
    return {"admin": email is not None, "email": email, "readonly": True}


def require_admin(request: Request) -> str | None:
    if not readonly_mode():
        return None
    email = iap_identity(request)
    if email is None:
        raise HTTPException(403, "admin sign-in required (IAP): use /admin/")
    return email
