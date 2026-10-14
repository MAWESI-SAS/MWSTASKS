/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Reemplaza hooks/oauth/extended de Plane (su punto de extensión para logins extra; en CE devuelve vacío).
 * Suma "Continue with Microsoft" si el backend tiene Microsoft configurado (GET /api/mawesi/auth-providers/).
 */
import { useEffect, useState } from "react";
import { API_BASE_URL, useSearchParams } from "../../plane";
import type { TOAuthConfigs } from "../../plane";
import { MicrosoftLogo } from "../../brand/microsoft-logo";

type TProviders = { microsoft: boolean };

// Un solo pedido por carga de página, aunque el hook se monte varias veces.
let providersPromise: Promise<TProviders> | null = null;
const loadProviders = (): Promise<TProviders> => {
  providersPromise ??= fetch(`${API_BASE_URL}/api/mawesi/auth-providers/`, { credentials: "include" })
    .then((r) => (r.ok ? (r.json() as Promise<TProviders>) : { microsoft: false }))
    .catch(() => ({ microsoft: false }));
  return providersPromise;
};

export const useExtendedOAuthConfig = (oauthActionText: string): TOAuthConfigs => {
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next_path");
  const [providers, setProviders] = useState<TProviders>({ microsoft: false });

  useEffect(() => {
    let alive = true;
    void loadProviders().then((p) => alive && setProviders(p));
    return () => {
      alive = false;
    };
  }, []);

  return {
    isOAuthEnabled: providers.microsoft,
    oAuthOptions: [
      {
        id: "microsoft",
        text: `${oauthActionText} with Microsoft`,
        icon: <MicrosoftLogo size={18} />,
        onClick: () => {
          const query = nextPath ? `?next_path=${encodeURIComponent(nextPath)}` : "";
          window.location.assign(`${API_BASE_URL}/auth/microsoft/${query}`);
        },
        enabled: providers.microsoft,
      },
    ],
  };
};
