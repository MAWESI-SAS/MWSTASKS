# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Settings de drf-spectacular para la documentación de la API (ver apidocs.py).

Va aparte porque lo importan los settings de Django: no puede importar vistas ni modelos.
"""

DESCRIPTION = """Todo lo que hace la web de MWSTASKS se puede hacer por API, con un **token personal**.

- **Cómo:** header `X-Api-Key: <token>`. El token se crea en Perfil → Personal Access Tokens.
- **Permisos:** los del dueño del token, en cada workspace y proyecto. Si le cambian el rol, el token cambia con él.
- **Lo que el token no hace:** crear, ver o borrar tokens; desactivar la cuenta; borrar un workspace.
- **Límite:** 60 pedidos por minuto por token (headers `X-RateLimit-Remaining` y `X-RateLimit-Reset`). Pasado eso: 429.
- **Cuál usar:** si existe en `/api/v1/…`, usá esa (es estable). Para el resto, `/api/…` (la de la web).
- **Guía con ejemplos:** `docs/API.md` en el repositorio MAWESI-SAS/MWSTASKS.
"""

SPECTACULAR_SETTINGS = {
    "TITLE": "API de MWSTASKS",
    "DESCRIPTION": DESCRIPTION,
    "VERSION": "1",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/",
    "COMPONENT_SPLIT_REQUEST": True,
    "PREPROCESSING_HOOKS": ["plane_mawesi.apidocs.preprocess"],
    "POSTPROCESSING_HOOKS": ["drf_spectacular.hooks.postprocess_schema_enums", "plane_mawesi.apidocs.postprocess"],
    "SERVERS": [{"url": "https://tasks.mawesi.online", "description": "Producción"}],
    "DISABLE_ERRORS_AND_WARNINGS": True,
    "SWAGGER_UI_DIST": "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14",
    "SWAGGER_UI_FAVICON_HREF": "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/favicon-32x32.png",
    "SWAGGER_UI_SETTINGS": {"persistAuthorization": False, "docExpansion": "none", "filter": True,
                            "tagsSorter": "alpha", "displayOperationId": False},
    "TAGS": [],
}
