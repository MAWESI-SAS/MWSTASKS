# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import os
import sys

# El paquete sin instalar (como lo corre el CI).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
