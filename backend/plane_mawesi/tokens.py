# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Token personal (PAT) en la API de la web: con el token se hace todo lo que hace la web, como su dueño.

- Plane acepta el token (`X-Api-Key`) solo en `/api/v1/` (82 rutas). La web usa `/api/…` y `/api/mawesi/…` (más de
  270 rutas) y ahí solo vale la sesión del navegador.
- `with_tokens()` vuelve a armar las rutas de la web con `TokenAuthentication` delante de la sesión. Las vistas no
  cambian: los permisos de Plane y los nuestros miran `request.user`, que con el token es su dueño. Así el token tiene
  justo los permisos del dueño, ni más ni menos, y si al dueño le cambian el rol, el token cambia con él.
- Mismo límite que `/api/v1/` (`ApiKeyRateThrottle`, un solo cupo por token), con los headers `X-RateLimit-*`
  (`RateLimitHeadersMiddleware`), y el mismo registro (`APITokenLogMiddleware` guarda cada pedido con token, sin el
  token en claro).
- Lo que el token no hace, aunque el dueño pueda (`DENIED`): manejar tokens (un token robado no puede crear otro ni
  borrar el de reemplazo), desactivar la cuenta y borrar un workspace. Eso queda solo para la web.
- No se tocan `/api/v1/` (ya acepta el token), `/api/instances/` (god-mode) ni `/api/public/` (páginas públicas).
"""
import re

from django.urls import URLPattern, URLResolver
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied

from plane.api.middleware.api_authentication import APIKeyAuthentication
from plane.api.rate_limit import ApiKeyRateThrottle

SKIP = ("api/v1/", "api/instances/", "api/public/")

# (métodos, ruta) que el token no puede usar; la ruta es `request.path` (con la barra inicial).
DENIED = (
    ({"GET", "POST", "PATCH", "PUT", "DELETE"}, re.compile(r"^/api/users/api-tokens/")),
    ({"DELETE"}, re.compile(r"^/api/users/me/$")),
    ({"DELETE"}, re.compile(r"^/api/workspaces/[^/]+/$")),
)
DENIED_MESSAGE = "Esto no se puede hacer con un token. Hacelo desde la web."


class TokenAuthentication(APIKeyAuthentication):
    """El `APIKeyAuthentication` de Plane (mismo header, mismas reglas de vencimiento) con la lista `DENIED`."""

    def authenticate(self, request):
        if not self.get_api_token(request):
            return None
        method = request.method.upper()
        if any(method in methods and rx.match(request.path) for methods, rx in DENIED):
            raise PermissionDenied(DENIED_MESSAGE)
        return super().authenticate(request)


def _view_class(callback):
    return getattr(callback, "cls", None) or getattr(callback, "view_class", None)


def accepts_session(callback) -> bool:
    cls = _view_class(callback)
    return bool(cls) and any(issubclass(a, SessionAuthentication) for a in getattr(cls, "authentication_classes", ()))


def _with_token(callback):
    cls = _view_class(callback)
    extra = {
        "authentication_classes": [TokenAuthentication, *cls.authentication_classes],
        "throttle_classes": [*cls.throttle_classes, ApiKeyRateThrottle],
    }
    if hasattr(callback, "actions"):  # ViewSet: as_view({"get": "list", ...})
        return cls.as_view(callback.actions, **{**callback.initkwargs, **extra})
    return cls.as_view(**{**callback.view_initkwargs, **extra})


def with_tokens(patterns, prefix=""):
    """Copia de `patterns` donde cada ruta de la web que acepta sesión acepta también el token."""
    out = []
    for p in patterns:
        route = prefix + str(p.pattern)
        if isinstance(p, URLResolver):
            if route.startswith(SKIP):
                out.append(p)
            else:
                out.append(URLResolver(p.pattern, with_tokens(p.url_patterns, route), p.default_kwargs,
                                       p.app_name, p.namespace))
        elif isinstance(p, URLPattern) and route.startswith("api/") and not route.startswith(SKIP) \
                and accepts_session(p.callback):
            out.append(URLPattern(p.pattern, _with_token(p.callback), p.default_args, p.name))
        else:
            out.append(p)
    return out


class RateLimitHeadersMiddleware:
    """`ApiKeyRateThrottle` deja el cupo en `request.META` y solo la base de `/api/v1/` lo pasa a la respuesta.
    Esto lo pasa en todas las rutas (en `/api/v1/` pone los mismos valores)."""

    HEADERS = ("X-RateLimit-Remaining", "X-RateLimit-Reset")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        for h in self.HEADERS:
            if h in request.META and h not in response:
                response[h] = request.META[h]
        return response
