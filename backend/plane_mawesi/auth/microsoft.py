# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Login con Microsoft Entra ID, sobre el molde OAuth de Plane (OauthAdapter).

Plane CE no trae Microsoft. Esta clase sigue el mismo contrato que GoogleOAuthProvider, así que el alta del
usuario, la sesión, ENABLE_SIGNUP y las invitaciones las sigue resolviendo Plane.

Configuración por variables de entorno (sin UI en god-mode):
  MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, MICROSOFT_TENANT_ID (GUID del tenant; "common" no se acepta)
  MICROSOFT_ALLOWED_DOMAINS (opcional, ej. "mawesi.net,mawesi.com": solo esos dominios de email)

Reglas de seguridad:
  - Solo cuentas del tenant configurado (claim `tid` del id_token) y que no sean invitados (userType Guest).
  - El email sale de Microsoft Graph (`mail` o `userPrincipalName`), que lo administra el tenant, no el usuario.
"""
import base64
import datetime
import json
import logging
import os
import re
from urllib.parse import urlencode

from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES, AuthenticationException
from plane.authentication.adapter.oauth import OauthAdapter

logger = logging.getLogger("plane.authentication")

PROVIDER = "microsoft"
GRAPH_ME = "https://graph.microsoft.com/v1.0/me?$select=id,mail,userPrincipalName,givenName,surname,userType"
SCOPE = "openid profile email User.Read"
GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def settings():
    """Config actual (se lee en cada pedido: cambiar el .env y reiniciar alcanza)."""
    domains = os.environ.get("MICROSOFT_ALLOWED_DOMAINS", "")
    return {
        "client_id": os.environ.get("MICROSOFT_CLIENT_ID", "").strip(),
        "client_secret": os.environ.get("MICROSOFT_CLIENT_SECRET", "").strip(),
        "tenant_id": os.environ.get("MICROSOFT_TENANT_ID", "").strip().lower(),
        "domains": {d.strip().lower() for d in domains.split(",") if d.strip()},
    }


def is_enabled() -> bool:
    s = settings()
    return bool(s["client_id"] and s["client_secret"] and GUID.match(s["tenant_id"]))


def fail(reason: str, code: str = "AUTHENTICATION_FAILED"):
    logger.warning("Login Microsoft rechazado: %s", reason)
    raise AuthenticationException(error_code=AUTHENTICATION_ERROR_CODES[code], error_message=code)


def jwt_claims(token: str) -> dict:
    """Claims del id_token SIN validar firma: llega directo del token endpoint de Microsoft por TLS y con
    nuestro client_secret (OpenID Connect Core 3.1.3.7 permite confiar en el TLS en este caso)."""
    try:
        payload = token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError, AttributeError):
        return {}


class MicrosoftOAuthProvider(OauthAdapter):
    provider = PROVIDER

    def __init__(self, request, code=None, state=None, callback=None):
        if not is_enabled():
            fail("no configurado (MICROSOFT_CLIENT_ID / MICROSOFT_CLIENT_SECRET / MICROSOFT_TENANT_ID)", "OAUTH_NOT_CONFIGURED")
        s = settings()
        self.tenant_id, self.allowed_domains = s["tenant_id"], s["domains"]
        base = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0"
        redirect_uri = f"{'https' if request.is_secure() else 'http'}://{request.get_host()}/auth/microsoft/callback/"
        auth_url = f"{base}/authorize?" + urlencode({
            "client_id": s["client_id"], "response_type": "code", "redirect_uri": redirect_uri,
            "response_mode": "query", "scope": SCOPE, "state": state, "prompt": "select_account",
        })
        super().__init__(request, PROVIDER, s["client_id"], SCOPE, redirect_uri, auth_url, f"{base}/token",
                         GRAPH_ME, s["client_secret"], code, callback=callback)

    def authentication_error_code(self):
        return "AUTHENTICATION_FAILED"

    def set_token_data(self):
        token = self.get_user_token(data={
            "client_id": self.client_id, "client_secret": self.client_secret, "code": self.code,
            "redirect_uri": self.redirect_uri, "grant_type": "authorization_code", "scope": SCOPE,
        })
        expires_in = token.get("expires_in")
        super().set_token_data({
            "access_token": token.get("access_token"),
            "refresh_token": token.get("refresh_token"),
            "access_token_expired_at": (
                datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=int(expires_in))
                if expires_in else None
            ),
            "refresh_token_expired_at": None,
            "id_token": token.get("id_token", ""),
        })

    def set_user_data(self):
        claims = jwt_claims(self.token_data.get("id_token") or "")
        if (claims.get("tid") or "").lower() != self.tenant_id:
            fail(f"tenant distinto ({claims.get('tid')!r})")
        me = self.get_user_response()
        if (me.get("userType") or "").lower() == "guest":
            fail("cuenta invitada (Guest) del tenant")
        email = (me.get("mail") or me.get("userPrincipalName") or "").strip().lower()
        if "@" not in email or "#ext#" in email:
            fail("cuenta sin email válido")
        if self.allowed_domains and email.rsplit("@", 1)[1] not in self.allowed_domains:
            fail(f"dominio no permitido ({email.rsplit('@', 1)[1]})")
        super().set_user_data({
            "email": email,
            "user": {
                "avatar": "",
                "first_name": me.get("givenName") or "",
                "last_name": me.get("surname") or "",
                "provider_id": claims.get("oid") or me.get("id"),
                "is_password_autoset": True,
            },
        })
