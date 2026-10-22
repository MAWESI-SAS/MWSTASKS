# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Ícono (favicon) de un sitio, para mostrarlo junto a los links como ClickUp.

Lo busca el servidor (no el navegador ni un servicio de terceros): así no se le cuenta a nadie qué links hay, y vale
para sitios que no tienen /favicon.ico (dev.azure.com) o que rechazan pedidos que no son de un navegador (se prueba
el dominio padre: tecnoquimicas.monday.com → monday.com).

Seguridad (el servidor hace pedidos a donde dice un usuario): solo http/https a nombres de dominio con IPs públicas,
cada redirección se vuelve a revisar, tiempo y tamaño máximos. Se guarda en caché (también cuando no hay ícono).
"""
import base64
import ipaddress
import re
import socket
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from django.core.cache import cache

TIMEOUT = 4
MAX_HTML = 512 * 1024
MAX_ICON = 200 * 1024
MAX_REDIRECTS = 3
TTL_FOUND = 7 * 24 * 3600
TTL_MISSING = 24 * 3600
HOST_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
# Sin Accept-Language algunos CDN (Akamai en azure.microsoft.com) dejan colgado el pedido.
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MWSTASKS/1.0; +favicon)", "Accept": "*/*", "Accept-Language": "es,en;q=0.8"}
MAGIC = {b"\x00\x00\x01\x00": "image/x-icon", b"\x89PNG": "image/png", b"GIF8": "image/gif", b"\xff\xd8\xff": "image/jpeg"}


def clean_host(value: str) -> Optional[str]:
    host = (value or "").strip().lower().rstrip(".")
    return host if HOST_RE.match(host) else None


def _resolve(host: str):
    return socket.getaddrinfo(host, None)


def _http_get(url: str):
    return requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True, allow_redirects=False)


def _public(host: str) -> bool:
    try:
        infos = _resolve(host)
    except (socket.gaierror, UnicodeError):
        return False
    return bool(infos) and all(ipaddress.ip_address(i[4][0].split("%")[0]).is_global for i in infos)


def _get(url: str, limit: int):
    """GET siguiendo redirecciones a mano (cada salto se revisa). Devuelve (respuesta, bytes) o None."""
    for _ in range(MAX_REDIRECTS + 1):
        u = urlparse(url)
        if u.scheme not in ("http", "https") or u.port not in (None, 80, 443) or not u.hostname:
            return None
        if not clean_host(u.hostname) or not _public(u.hostname):
            return None
        try:
            r = _http_get(url)
        except requests.RequestException:
            return None
        with r:
            if r.is_redirect and r.headers.get("location"):
                url = urljoin(url, r.headers["location"])
                continue
            if r.status_code != 200:
                return None
            body = b""
            for chunk in r.iter_content(16384):
                body += chunk
                if len(body) > limit:
                    return None
            return r, body
    return None


class _IconLinks(HTMLParser):
    """<link rel="icon"> del <head>, en orden de preferencia (los de Apple al final; sin mask-icon ni fluid-icon)."""

    def __init__(self):
        super().__init__()
        self.found = []

    def handle_starttag(self, tag, attrs):
        if tag != "link":
            return
        a = dict(attrs)
        rel = set((a.get("rel") or "").lower().split())
        href = a.get("href")
        if not href or "icon" not in " ".join(rel) or rel & {"mask-icon", "fluid-icon"}:
            return
        apple = any(r.startswith("apple-touch-icon") for r in rel)
        self.found.append((1 if apple else 0, href))


def _image_type(content_type: str, body: bytes) -> Optional[str]:
    for magic, kind in MAGIC.items():
        if body.startswith(magic):
            return kind
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct == "image/svg+xml" or (ct in ("", "text/plain", "text/xml", "application/xml") and b"<svg" in body[:1024]):
        return "image/svg+xml"
    return ct if ct.startswith("image/") else None


def _data_uri(href: str):
    m = re.match(r"^data:(image/[a-z0-9.+-]+);base64,(.+)$", href, re.I | re.S)
    if not m:
        return None
    try:
        body = base64.b64decode(m.group(2), validate=False)
    except ValueError:
        return None
    return (body, m.group(1).lower()) if 0 < len(body) <= MAX_ICON else None


def _from_site(host: str):
    candidates = []
    page = _get(f"https://{host}/", MAX_HTML)
    base = f"https://{host}/"
    if page:
        resp, body = page
        base = resp.url
        parser = _IconLinks()
        try:
            parser.feed(body.decode(resp.encoding or "utf-8", errors="replace"))
        except Exception:  # noqa: BLE001 - HTML roto: se prueba /favicon.ico igual
            pass
        candidates = [href for _, href in sorted(parser.found, key=lambda x: x[0])]
    candidates.append("/favicon.ico")
    for href in candidates[:6]:
        if href.startswith("data:"):
            found = _data_uri(href)
            if found:
                return found
            continue
        got = _get(urljoin(base, href), MAX_ICON)
        if got:
            kind = _image_type(got[0].headers.get("content-type", ""), got[1])
            if kind and got[1]:
                return got[1], kind
    return None


def icon(host: str):
    """(bytes, content_type) o None. Prueba el sitio y después el dominio padre."""
    key = f"mawesi:favicon:{host}"
    hit = cache.get(key)
    if hit is not None:
        return hit or None
    labels = host.split(".")
    tries = [host] + ([".".join(labels[1:])] if len(labels) > 2 else [])
    found = None
    for h in tries:
        found = _from_site(h)
        if found:
            break
    cache.set(key, found or False, TTL_FOUND if found else TTL_MISSING)
    return found
