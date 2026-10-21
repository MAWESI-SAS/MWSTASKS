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
import "./board/card-style.css";
import { registerNav, registerProjectSettings, registerWikiNav, registerWorkspaceSettings } from "./nav";

registerNav();
registerWikiNav();
registerProjectSettings();
registerWorkspaceSettings();
(globalThis as Record<string, unknown>).__MAWESI_EXT__ = "MAWESI-REGISTER-OK";
