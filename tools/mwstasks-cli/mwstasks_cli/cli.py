# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""`mws`: CLI de MWSTASKS para personas y agentes. Ver `mws guide`.

Salida: JSON en stdout. Errores: JSON en stderr y código de salida
0 bien · 2 uso o parámetro que falta · 3 token inválido · 4 sin permiso, no existe o datos mal · 5 servidor o red.
"""
import argparse
import json
import os
import sys
import urllib.error

from mwstasks_cli import __version__, helpers, schema
from mwstasks_cli.client import ApiError, Client
from mwstasks_cli.resolve import MissingParam, Resolver

DEFAULT_URL = "https://tasks.mawesi.online"
GUIDE = os.path.join(os.path.dirname(__file__), "GUIDE.md")


# Atajos del CLI que conviene sugerir cuando la búsqueda los nombra (son varios pasos por API).
TIPS = (
    (("adjunt", "attach", "archivo", "subir"), "Para adjuntar un archivo a una tarea: `mws attach TQ-123 <archivo>`."),
    (("pagina", "page", "wiki", "contenido", "escribir"),
     "Para escribir el contenido de una Página: `mws page-write <page_id> --project TQ --html @archivo.html`."),
)


class UsageError(Exception):
    pass


def emit(data, compact=False):
    print(json.dumps(data, ensure_ascii=False, indent=None if compact else 2, default=str))


def fail(code, error, **extra):
    print(json.dumps({"error": error, **extra}, ensure_ascii=False, default=str), file=sys.stderr)
    return code


def token():
    value = os.environ.get("MWSTASKS_TOKEN")
    if not value and os.environ.get("MWSTASKS_TOKEN_FILE"):
        with open(os.environ["MWSTASKS_TOKEN_FILE"], encoding="utf-8") as f:
            value = f.read().strip()
    if not value:
        raise UsageError("Falta el token: variable MWSTASKS_TOKEN (o MWSTASKS_TOKEN_FILE con la ruta a un archivo).")
    return value


def parse_pairs(pairs):
    """`clave=valor` → dict. Repetir la clave arma una lista (`assignee=a assignee=b`)."""
    out = {}
    for p in pairs or []:
        if "=" not in p:
            raise UsageError(f"«{p}» no es clave=valor.")
        k, v = p.split("=", 1)
        if k in out:
            out[k] = (out[k] if isinstance(out[k], list) else [out[k]]) + [v]
        else:
            out[k] = v
    return out


def json_value(text):
    try:
        return json.loads(text)
    except ValueError:
        return text


def read_text(arg):
    """Texto directo, `@archivo` o `-` (stdin)."""
    if arg == "-":
        return sys.stdin.read()
    if arg.startswith("@"):
        with open(arg[1:], encoding="utf-8") as f:
            return f.read()
    return arg


def build_body(args):
    body = None
    if args.body is not None:
        try:
            body = json.loads(read_text(args.body))
        except ValueError as e:
            raise UsageError(f"--body no es JSON válido: {e}")
    for k, v in parse_pairs(args.data).items():
        body = body if isinstance(body, dict) else {}
        body[k] = [json_value(x) for x in v] if isinstance(v, list) else json_value(v)
    return body


def add_request_args(p):
    p.add_argument("params", nargs="*", metavar="clave=valor",
                   help="parámetros de la ruta (project=TQ, issue=TQ-123, cycle_id=…); lo que sobra va a ?query")
    p.add_argument("-d", "--data", action="append", metavar="campo=valor",
                   help="campo del cuerpo JSON (el valor se lee como JSON si se puede: 5, true, [\"a\"], null)")
    p.add_argument("--body", metavar="JSON|@archivo|-", help="cuerpo JSON completo")
    p.add_argument("--file", action="append", metavar="campo=ruta", help="sube un archivo (multipart)")
    p.add_argument("--all", action="store_true", help="trae todas las páginas de una lista")
    p.add_argument("--dry-run", action="store_true", help="muestra el pedido sin hacerlo")


def parser():
    ap = argparse.ArgumentParser(prog="mws", description="CLI de MWSTASKS. Empezá por `mws guide`.")
    ap.add_argument("--compact", action="store_true", help="JSON en una línea")
    ap.add_argument("--version", action="version", version=__version__)
    # --compact vale también después del comando (`mws ops --compact`).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--compact", action="store_true", default=argparse.SUPPRESS, help="JSON en una línea")
    sub = ap.add_subparsers(dest="cmd", required=True)
    _add = sub.add_parser
    sub.add_parser = lambda *a, **k: _add(*a, parents=[common], **k)
    sub.add_parser("guide", help="cómo usar el CLI (para agentes)")
    sub.add_parser("whoami", help="dueño del token y sus workspaces")
    o = sub.add_parser("ops", help="buscar operaciones (todas las de la API)")
    o.add_argument("words", nargs="*", help="palabras a buscar (sin tildes ni mayúsculas)")
    o.add_argument("--tag", default="", help="solo un grupo (p. ej. Horas, Tareas, Ciclos)")
    o.add_argument("--tags", action="store_true", help="lista los grupos con cuántas operaciones tienen")
    o.add_argument("--limit", type=int, default=50)
    o.add_argument("--refresh", action="store_true", help="volver a pedir el schema al servidor")
    d = sub.add_parser("op", help="detalle de una operación: parámetros, ejemplo de cuerpo, quién puede")
    d.add_argument("ref", help='id de la operación o "MÉTODO /ruta"')
    r = sub.add_parser("run", help="ejecutar una operación del schema")
    r.add_argument("ref", help='id de la operación o "MÉTODO /ruta"')
    add_request_args(r)
    c = sub.add_parser("call", help="llamar cualquier ruta, esté o no en el schema")
    c.add_argument("method", help="GET, POST, PUT, PATCH o DELETE")
    c.add_argument("path", help="ruta con o sin {parámetros}: /api/workspaces/{slug}/projects/")
    add_request_args(c)
    a = sub.add_parser("attach", help="adjuntar un archivo a una tarea")
    a.add_argument("issue", help="clave (TQ-123) o UUID")
    a.add_argument("path", help="archivo")
    a.add_argument("--project", help="proyecto, si la tarea va por UUID")
    w = sub.add_parser("page-write", help="reemplazar el contenido (HTML) de una Página")
    w.add_argument("page_id")
    w.add_argument("--project", required=True, help="identificador (TQ) o UUID")
    w.add_argument("--html", required=True, metavar="HTML|@archivo|-")
    return ap


def ctx():
    client = Client(os.environ.get("MWSTASKS_URL", DEFAULT_URL), token())
    return client, Resolver(client, os.environ.get("MWSTASKS_WORKSPACE"))


def ops_of(client, refresh=False):
    return schema.operations(schema.load(client, refresh=refresh))


def do_request(client, resolver, method, path, args):
    real, query = resolver.fill(path, parse_pairs(args.params))
    body = build_body(args)
    files = parse_pairs(args.file) if args.file else None
    if args.dry_run:
        return {"dry_run": True, "method": method, "url": client.absolute(real, query), "body": body, "files": files}
    if args.all and method == "GET":
        return client.paginate(method, real, query)
    form = body if files and isinstance(body, dict) else None
    status, _, data = client.request(method, real, query=query, body=None if files else body, files=files, form=form)
    return data if data is not None else {"status": status}


def run(argv=None):
    args = parser().parse_args(argv)
    if args.cmd == "guide":
        with open(GUIDE, encoding="utf-8") as f:
            print(f.read())
        return 0
    client, resolver = ctx()
    if args.cmd == "whoami":
        _, _, me = client.request("GET", "/api/users/me/")
        _, _, ws = client.request("GET", "/api/users/me/workspaces/")
        emit({"id": me.get("id"), "email": me.get("email"), "display_name": me.get("display_name"),
              "workspaces": [{"slug": w.get("slug"), "name": w.get("name"), "role": w.get("role")} for w in ws or []],
              "default_workspace": resolver.workspace}, args.compact)
    elif args.cmd == "ops":
        ops = ops_of(client, args.refresh)
        if args.tags:
            counts = {}
            for op in ops:
                counts[op.tag] = counts.get(op.tag, 0) + 1
            emit({"total": len(ops), "tags": dict(sorted(counts.items()))}, args.compact)
        else:
            words = " ".join(args.words)
            found = schema.search(ops, words, args.tag)
            out = {"total": len(found), "shown": min(len(found), args.limit), "ops": [op.brief() for op in found[:args.limit]]}
            tips = [tip for keys, tip in TIPS if any(k in schema.plain(words) for k in keys)]
            if not found:
                tips.append("Probá otras palabras (también en inglés), `mws ops --tags`, o `mws call MÉTODO /ruta`.")
            if tips:
                out["tips"] = tips
            emit(out, args.compact)
    elif args.cmd == "op":
        op = schema.find(ops_of(client), args.ref)
        if op is None:
            raise UsageError(f"No existe la operación «{args.ref}». Buscala con `mws ops <palabras>`.")
        emit(op.detail(), args.compact)
    elif args.cmd == "run":
        op = schema.find(ops_of(client), args.ref)
        if op is None:
            raise UsageError(f"No existe la operación «{args.ref}». Buscala con `mws ops <palabras>`, "
                             "o usá `mws call MÉTODO /ruta`.")
        emit(do_request(client, resolver, op.method, op.path, args), args.compact)
    elif args.cmd == "call":
        emit(do_request(client, resolver, args.method.upper(), args.path, args), args.compact)
    elif args.cmd == "attach":
        emit(helpers.attach(client, resolver, args.issue, args.path, project_ref=args.project), args.compact)
    elif args.cmd == "page-write":
        emit(helpers.write_page(client, resolver, args.project, args.page_id, read_text(args.html)), args.compact)
    return 0


def main(argv=None):
    try:
        return run(argv)
    except (UsageError, MissingParam) as e:
        return fail(2, str(e))
    except ApiError as e:
        detail = e.body
        if e.status == 401 or (e.status == 403 and "token" in json.dumps(detail).lower() and "not valid" in json.dumps(detail).lower()):
            return fail(3, "Token inválido, vencido o borrado.", status=e.status, detail=detail)
        if e.status >= 500:
            return fail(5, "Error del servidor.", status=e.status, method=e.method, url=e.url, detail=detail)
        return fail(4, "El servidor rechazó el pedido.", status=e.status, method=e.method, url=e.url, detail=detail)
    except FileNotFoundError as e:
        return fail(2, f"No existe el archivo: {e.filename}")
    except (urllib.error.URLError, OSError) as e:
        return fail(5, f"No pude conectar: {e}")


if __name__ == "__main__":
    sys.exit(main())
