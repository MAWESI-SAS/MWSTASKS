# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import pytest
from django.core.cache import cache

from plane_mawesi import favicons as F
from plane_mawesi.tests.conftest import MEMBER

PNG = b"\x89PNG\r\n\x1a\nfake"
ICO = b"\x00\x00\x01\x00fake"


class Fake:
    def __init__(self, url, status=200, body=b"", headers=None):
        self.url, self.status_code, self._body, self.headers, self.encoding = url, status, body, headers or {}, "utf-8"
        self.is_redirect = status in (301, 302, 307, 308)

    def iter_content(self, n):
        yield self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def web(monkeypatch):
    """Internet de mentira: {url: Fake}; las IPs de cada dominio en `ips` (por defecto, una pública)."""
    pages, ips, asked = {}, {}, []

    def get(url):
        asked.append(url)
        return pages.get(url) or Fake(url, 404)

    def resolve(host):
        return [(2, 1, 6, "", (ips.get(host, "93.184.216.34"), 0))]

    monkeypatch.setattr(F, "_http_get", get)
    monkeypatch.setattr(F, "_resolve", resolve)
    cache.clear()
    yield pages, ips, asked
    cache.clear()


def test_solo_nombres_de_dominio():
    assert F.clean_host("Dev.Azure.com.") == "dev.azure.com"
    for bad in ("localhost", "10.0.0.1", "[::1]", "a b.com", "x.com:8080", "", "http://x.com"):
        assert F.clean_host(bad) is None


def test_icono_del_html_y_luego_favicon_ico(web):
    pages, _, _ = web
    pages["https://dev.azure.com/"] = Fake("https://dev.azure.com/", 302, headers={"location": "https://azure.microsoft.com/devops"})
    pages["https://azure.microsoft.com/devops"] = Fake(
        "https://azure.microsoft.com/devops",
        body=b'<html><head><link rel="mask-icon" href="/m.svg"><link rel="apple-touch-icon" href="/a.png">'
             b'<link rel="icon" href="/favicon.ico?v2"></head></html>')
    pages["https://azure.microsoft.com/favicon.ico?v2"] = Fake("x", body=ICO, headers={"content-type": "text/plain"})
    assert F.icon("dev.azure.com") == (ICO, "image/x-icon")


def test_prueba_el_dominio_padre_y_guarda_en_cache(web):
    pages, _, asked = web
    pages["https://monday.com/favicon.ico"] = Fake("x", body=PNG, headers={"content-type": "image/png"})
    assert F.icon("tecnoquimicas.monday.com") == (PNG, "image/png")
    n = len(asked)
    assert F.icon("tecnoquimicas.monday.com") == (PNG, "image/png") and len(asked) == n
    assert F.icon("nada.example.org") is None and F.icon("nada.example.org") is None


def test_no_va_a_ips_privadas_ni_por_redireccion(web):
    pages, ips, asked = web
    ips["intranet.mawesi.online"] = "100.75.189.174"
    ips["mawesi.online"] = "100.75.189.174"
    assert F.icon("intranet.mawesi.online") is None and asked == []
    ips["interno.example.com"] = "192.168.1.10"
    pages["https://malo.example.com/"] = Fake("https://malo.example.com/", 302, headers={"location": "https://interno.example.com/"})
    pages["https://malo.example.com/favicon.ico"] = Fake("x", 302, headers={"location": "http://interno.example.com/favicon.ico"})
    assert F.icon("malo.example.com") is None
    assert not any("interno" in u for u in asked)


def test_no_acepta_lo_que_no_es_imagen_ni_archivos_grandes(web):
    pages, _, _ = web
    pages["https://a.example.com/favicon.ico"] = Fake("x", body=b"<html>login</html>", headers={"content-type": "text/html"})
    assert F.icon("a.example.com") is None
    pages["https://b.example.com/favicon.ico"] = Fake("x", body=PNG + b"0" * F.MAX_ICON, headers={"content-type": "image/png"})
    assert F.icon("b.example.com") is None


@pytest.mark.django_db
class TestEndpoint:
    def url(self, ws, host):
        return f"/api/mawesi/workspaces/{ws.slug}/favicon/?host={host}"

    def test_devuelve_la_imagen_con_cabeceras_seguras(self, web, member_factory, workspace):
        pages, _, _ = web
        pages["https://github.com/favicon.ico"] = Fake("x", body=b"<svg xmlns='http://www.w3.org/2000/svg'/>", headers={"content-type": "image/svg+xml"})
        _, c = member_factory("ana@example.com", MEMBER)
        r = c.get(self.url(workspace, "github.com"))
        assert r.status_code == 200 and r["Content-Type"] == "image/svg+xml"
        assert "sandbox" in r["Content-Security-Policy"] and r["X-Content-Type-Options"] == "nosniff"
        assert c.get(self.url(workspace, "sin-icono.example.com")).status_code == 404
        assert c.get(self.url(workspace, "10.0.0.1")).status_code == 400

    def test_solo_miembros(self, web, workspace):
        from rest_framework.test import APIClient

        from plane_mawesi.tests.conftest import make_user

        other = make_user("otro@example.com")
        c = APIClient()
        c.force_authenticate(user=other)
        assert c.get(self.url(workspace, "github.com")).status_code == 403
