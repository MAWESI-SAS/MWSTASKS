# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Alta, cambios y baja de empleados AI como usuarios de MWSTASKS. Ver `plane_mawesi/agents.py`.

  docker compose exec -T mwstasks-api python manage.py mawesi_agents --workspace mawesi < agentes.json > tokens.jsonl

Entrada (stdin): JSON [{"email", "name", "title", "projects": ["*"] | ["TQ", ...], "avatar_b64", "active"}].
Salida (stdout): una línea JSON {"email", "token"} por cada token NUEVO; el resumen va a stderr, para que los tokens
se puedan mandar directo a Vault sin pasar por la pantalla. `--rotate` desactiva los tokens actuales y crea otros.
"""
import json
import sys

from django.core.management.base import BaseCommand, CommandError

from plane.db.models import Workspace

from plane_mawesi.agents import Agent, sync_agent


class Command(BaseCommand):
    help = "Crea o actualiza empleados AI (usuario, avatar, proyectos y token) desde un JSON por stdin."

    def add_arguments(self, parser):
        parser.add_argument("--workspace", required=True)
        parser.add_argument("--rotate", action="store_true", help="Crea tokens nuevos y desactiva los actuales.")

    def handle(self, *args, workspace, rotate, **options):
        ws = Workspace.objects.filter(slug=workspace).first()
        if ws is None:
            raise CommandError(f"No existe el workspace {workspace}")
        try:
            agents = [Agent.from_dict(d) for d in json.load(sys.stdin)]
        except (ValueError, TypeError, KeyError) as e:
            raise CommandError(f"Entrada inválida: {e}") from e
        for agent in agents:
            r = sync_agent(ws, agent, rotate=rotate)
            if r.token:
                self.stdout.write(json.dumps({"email": r.email, "token": r.token}))
            state = "baja" if not agent.active else ("nuevo" if r.created else "ya existía")
            self.stderr.write(f"{r.email}: {state} | avatar {'sí' if r.avatar else 'igual'} | "
                              f"proyectos {','.join(r.projects) or '-'} | token {'nuevo' if r.token else 'igual'}")
