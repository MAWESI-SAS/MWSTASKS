# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Settings de Plane MAWESI.

Se activa SOLO con la variable de entorno DJANGO_SETTINGS_MODULE=plane_mawesi.settings
(todos los entrypoints de Plane usan os.environ.setdefault). No edita ningún archivo de Plane.

Importar `plane` ejecuta plane/__init__.py -> plane/celery.py, que lee settings de Django al
importarse (redis_instance()). Si en ese momento DJANGO_SETTINGS_MODULE apunta a este módulo,
Django lo vuelve a importar a medio cargar y falla (p. ej. falta REDIS_SSL). Por eso, mientras
importamos los settings de Plane, la variable apunta a los oficiales; al terminar vuelve a la
nuestra y Django reemplaza esa carga temprana por este módulo completo (LazySettings limpia su
caché al asignar _wrapped).
"""
import os

_OURS = os.environ.get("DJANGO_SETTINGS_MODULE", "plane_mawesi.settings")
os.environ["DJANGO_SETTINGS_MODULE"] = "plane.settings.production"
try:
    from plane.settings.production import *  # noqa: F401,F403,E402
    from plane.settings.production import INSTALLED_APPS  # noqa: E402
finally:
    os.environ["DJANGO_SETTINGS_MODULE"] = _OURS

INSTALLED_APPS = [*INSTALLED_APPS, "plane_mawesi"]
ROOT_URLCONF = "plane_mawesi.urls"

# Documentación de la API (/api/mawesi/docs/): drf-spectacular ya viene en la imagen de Plane (ver apidocs.py).
if "drf_spectacular" not in INSTALLED_APPS:
    INSTALLED_APPS.append("drf_spectacular")
# Headers del límite del token también en las rutas de la web (ver tokens.py).
MIDDLEWARE = [*MIDDLEWARE, "plane_mawesi.tokens.RateLimitHeadersMiddleware"]  # noqa: F405
# Rutas de la API sin la barra final, sin redirigir (ver slashes.py): antes de CommonMiddleware (APPEND_SLASH).
_common = MIDDLEWARE.index("django.middleware.common.CommonMiddleware")
MIDDLEWARE = [*MIDDLEWARE[:_common], "plane_mawesi.slashes.SlashlessApiMiddleware", *MIDDLEWARE[_common:]]
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_SCHEMA_CLASS": "plane_mawesi.apidocs.SafeAutoSchema"}  # noqa: F405
from plane_mawesi.apidocs_settings import SPECTACULAR_SETTINGS  # noqa: E402,F401
