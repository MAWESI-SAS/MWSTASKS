# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Settings de test: los de test de Plane + nuestra app (mismo truco de importación que settings.py)."""
import os

_OURS = os.environ.get("DJANGO_SETTINGS_MODULE", "plane_mawesi.settings_test")
os.environ["DJANGO_SETTINGS_MODULE"] = "plane.settings.test"
try:
    from plane.settings.test import *  # noqa: F401,F403,E402
    from plane.settings.test import INSTALLED_APPS  # noqa: E402
finally:
    os.environ["DJANGO_SETTINGS_MODULE"] = _OURS

INSTALLED_APPS = [*INSTALLED_APPS, "plane_mawesi"]
ROOT_URLCONF = "plane_mawesi.urls"
# Plane arma los links de los avisos con WEB_URL (en prod viene del .env).
WEB_URL = "http://localhost"
