/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Se inyecta al inicio de app/entry.client.tsx (plugin de vite.ext.config.ts).
 */
import "./theme/fonts.css";
import "./theme/mawesi-theme.generated.css";
import "./theme/shell.css";
import "./folders/tree.css";
import { registerNav, registerProjectSettings, registerWikiNav } from "./nav";

registerNav();
registerWikiNav();
registerProjectSettings();
(globalThis as Record<string, unknown>).__MAWESI_EXT__ = "MAWESI-REGISTER-OK";
