# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""La API también responde sin la barra final (`/api/users/me` = `/api/users/me/`).

Las rutas de Plane terminan en `/`. Sin ella, `CommonMiddleware` de Django (APPEND_SLASH) responde 301 a la ruta con
barra, también a un POST. Un cliente que no sigue redirecciones con el token (a propósito, para no mandarlo a otro lado)
o que arma las rutas sin la barra, como la fábrica de paquetes de AI_EMPLOYEES, falla en todas. Esto atiende la ruta con
barra directo, sin redirigir, solo cuando la ruta sin barra no existe y la ruta con barra sí. Va antes de
`CommonMiddleware`.
"""
from django.urls import Resolver404, resolve


class SlashlessApiMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        if path.startswith("/api/") and not path.endswith("/"):
            urlconf = getattr(request, "urlconf", None)
            try:
                resolve(path, urlconf)
            except Resolver404:
                try:
                    resolve(f"{path}/", urlconf)
                except Resolver404:
                    pass
                else:
                    request.path_info = f"{path}/"
                    request.path = f"{request.path}/"
        return self.get_response(request)
