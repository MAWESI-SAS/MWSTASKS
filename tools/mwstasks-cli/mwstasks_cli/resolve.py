# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Arma la ruta real de una operación a partir de `clave=valor`, con atajos para agentes:

- `slug`: si no viene, el workspace de MWSTASKS_WORKSPACE (o `workspace=`).
- `project=TQ` (identificador) o `project=<uuid>` → `project_id`.
- `issue=TQ-123` (clave) o `issue=<uuid>` → `issue_id` (y `project_id`), y también el `{pk}` de `…/issues/{pk}/`.
- `{x_id}` acepta `x_id=` o `x=` (por ejemplo `cycle=` para `{cycle_id}`).
Lo que sobra va como parámetro de la URL (`?clave=valor`).
"""
import re
import urllib.parse

from mwstasks_cli.schema import PARAM

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
ISSUE_KEY = re.compile(r"^([A-Za-z0-9]+)-(\d+)$")
ISSUE_SEGMENTS = ("issues", "work-items", "issue", "epics")


class MissingParam(ValueError):
    pass


class Resolver:
    def __init__(self, client, workspace=None):
        self.client, self.workspace = client, workspace
        self._projects = None
        self._issues = {}

    def projects(self, slug):
        if self._projects is None:
            _, _, data = self.client.request("GET", f"/api/workspaces/{slug}/projects/")
            self._projects = data if isinstance(data, list) else (data or {}).get("results", [])
        return self._projects

    def project_id(self, slug, ref):
        if UUID.match(ref):
            return ref
        for p in self.projects(slug):
            if str(p.get("identifier", "")).upper() == ref.upper():
                return str(p["id"])
        raise MissingParam(f"No encuentro el proyecto «{ref}» en el workspace «{slug}» (o el dueño del token no es miembro).")

    def issue(self, slug, ref):
        """{"id", "project_id", "project_identifier", "sequence_id"} de una tarea por clave (TQ-123) o UUID."""
        if ref in self._issues:
            return self._issues[ref]
        if UUID.match(ref):
            out = {"id": ref}
        else:
            m = ISSUE_KEY.match(ref)
            if not m:
                raise MissingParam(f"«{ref}» no es una tarea: usá la clave (TQ-123) o el UUID.")
            _, _, data = self.client.request("GET", f"/api/v1/workspaces/{slug}/issues/{m.group(1).upper()}-{m.group(2)}/")
            out = {"id": str(data["id"]), "project_id": str(data.get("project") or data.get("project_id")),
                   "project_identifier": m.group(1).upper(), "sequence_id": m.group(2)}
        self._issues[ref] = out
        return out

    def fill(self, path, args):
        """(ruta con los valores, parámetros sobrantes). `args` es {clave: texto} y no se modifica."""
        args = dict(args)
        slug = args.pop("slug", None) or args.pop("workspace", None) or self.workspace
        names = PARAM.findall(path)
        values = {}
        issue_ref = args.pop("issue", None)
        project_ref = args.pop("project", None)
        issue = None
        if "slug" in names:
            if not slug:
                raise MissingParam("Falta el workspace: `slug=<slug>` o la variable MWSTASKS_WORKSPACE.")
            values["slug"] = slug
        if issue_ref and any(n in names for n in ("issue_id", "pk", "project_identifier", "issue_identifier", "project_id")):
            issue = self.issue(slug, issue_ref)
        for name in names:
            if name in values:
                continue
            if name in args:
                values[name] = args.pop(name)
            elif name == "project_id" and project_ref:
                values[name] = self.project_id(slug, project_ref)
            elif name == "project_id" and issue and issue.get("project_id"):
                values[name] = issue["project_id"]
            elif name == "issue_id" and issue:
                values[name] = issue["id"]
            elif name == "pk" and issue and self._segment_before(path, name) in ISSUE_SEGMENTS:
                values[name] = issue["id"]
            elif name in ("project_identifier", "issue_identifier") and issue and "sequence_id" in issue:
                values[name] = issue["project_identifier"] if name == "project_identifier" else issue["sequence_id"]
            elif name.endswith("_id") and name[:-3] in args:
                values[name] = args.pop(name[:-3])
            elif name == "pk" and "id" in args:
                values[name] = args.pop("id")
        missing = [n for n in names if n not in values]
        if missing:
            raise MissingParam("Faltan parámetros de la ruta: " + ", ".join(missing)
                               + ". Pasalos como clave=valor (ver `mws op <id>`).")
        if project_ref and "project_id" not in names:
            args["project"] = self.project_id(slug, project_ref)  # filtro ?project=<uuid> (p. ej. tareas del workspace)
        if issue_ref and not issue:
            args["issue"] = issue_ref
        real = PARAM.sub(lambda m: urllib.parse.quote(str(values[m.group(1)]), safe=""), path)
        return real, args

    @staticmethod
    def _segment_before(path, name):
        parts = path.strip("/").split("/")
        i = parts.index("{" + name + "}")
        return parts[i - 1] if i else ""
