# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""HTTP contra MWSTASKS con el token personal. Solo biblioteca estándar.

- Espera solo cuando el servidor dice 429 (límite por minuto) y reintenta.
- Pagina siguiendo `next_cursor` de Plane.
- Sube archivos con multipart (logo del proyecto, el paso a S3 de los adjuntos).
"""
import json
import mimetypes
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from mwstasks_cli import __version__

MAX_RETRIES_429 = 5
MAX_WAIT_429 = 90  # segundos
PAGE_SIZE = 100
MAX_PAGES = 500


class ApiError(Exception):
    def __init__(self, status, body, method, url):
        super().__init__(f"{method} {url} → {status}")
        self.status, self.body, self.method, self.url = status, body, method, url


def _decode(raw, content_type):
    if not raw:
        return None
    if "json" in (content_type or ""):
        try:
            return json.loads(raw)
        except ValueError:
            pass
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"binary_bytes": len(raw)}


def multipart(fields, files):
    """(cuerpo, content-type) para `fields` {nombre: texto} y `files` {nombre: ruta}."""
    boundary = uuid.uuid4().hex
    out = []
    for k, v in (fields or {}).items():
        out.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, path in (files or {}).items():
        name = os.path.basename(path)
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            data = f.read()
        out.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{name}"\r\n'
                   f"Content-Type: {ctype}\r\n\r\n".encode() + data + b"\r\n")
    out.append(f"--{boundary}--\r\n".encode())
    return b"".join(out), f"multipart/form-data; boundary={boundary}"


class Client:
    def __init__(self, url, token, timeout=120, sleep=None):
        self.url, self.token, self.timeout = url.rstrip("/"), token, timeout
        self.sleep = sleep or (lambda s: time.sleep(s))

    def absolute(self, path, query=None):
        url = path if path.startswith(("http://", "https://")) else self.url + "/" + path.lstrip("/")
        if query:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(query, doseq=True)
        return url

    def request(self, method, path, query=None, body=None, files=None, form=None, auth=True):
        """(status, headers, datos). Lanza ApiError si el servidor responde 4xx/5xx."""
        method, url = method.upper(), self.absolute(path, query)
        headers = {"User-Agent": f"mwstasks-cli/{__version__}", "Accept": "application/json"}
        if auth:
            headers["X-Api-Key"] = self.token
        data = None
        if files or form:
            data, headers["Content-Type"] = multipart(form, files)
        elif body is not None:
            data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
        for attempt in range(MAX_RETRIES_429 + 1):
            req = urllib.request.Request(url, data=data, method=method, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return r.status, dict(r.headers), _decode(r.read(), r.headers.get("Content-Type"))
            except urllib.error.HTTPError as e:
                payload = _decode(e.read(), e.headers.get("Content-Type"))
                if e.code == 429 and attempt < MAX_RETRIES_429:
                    self.sleep(self._wait(e.headers))
                    continue
                raise ApiError(e.code, payload, method, url) from None
        raise AssertionError("no llega")

    @staticmethod
    def _wait(headers):
        reset, retry = headers.get("X-RateLimit-Reset"), headers.get("Retry-After")
        try:
            if retry:
                return min(MAX_WAIT_429, max(1, float(retry)))
            if reset:
                return min(MAX_WAIT_429, max(1, float(reset) - time.time()))
        except ValueError:
            pass
        return 10

    def paginate(self, method, path, query=None):
        """Todas las páginas de una lista de Plane (`results` + `next_cursor`). Si no es paginada, la devuelve igual."""
        query = dict(query or {})
        query.setdefault("per_page", PAGE_SIZE)
        rows = []
        for _ in range(MAX_PAGES):
            _, _, data = self.request(method, path, query=query)
            if not (isinstance(data, dict) and "results" in data and "next_cursor" in data):
                return data
            results = data["results"]
            rows.extend(results if isinstance(results, list) else [results])
            if not data.get("next_page_results"):
                return rows
            query["cursor"] = data["next_cursor"]
        return rows
