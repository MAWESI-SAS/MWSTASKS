/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Bloque "Logo con imagen" en Configuración > General del proyecto (solo admins). La imagen se achica en el
 * navegador (resize.ts) y se sube a /api/mawesi/…/logo/. Después se vuelve a leer el proyecto: el logo cambia en
 * el menú, las migas y el inicio sin recargar.
 */
import { useRef, useState } from "react";
import { observer } from "mobx-react";
import { Button, TOAST_TYPE, setToast, useProject } from "../plane";
import type { TLogoProps } from "../plane";
import { useT } from "../i18n";
import { Logo, logoImageUrl } from "./logo";
import { squareLogo } from "./resize";
import { projectLogoService } from "./service";

type Props = { workspaceSlug: string; projectId: string; logo: TLogoProps | undefined };

export const ProjectLogoUpload = observer(function ProjectLogoUpload({ workspaceSlug, projectId, logo }: Props) {
  const t = useT();
  const { fetchProjectDetails } = useProject();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<"upload" | "remove" | null>(null);
  const hasImage = !!logoImageUrl(logo);

  const run = async (kind: "upload" | "remove", action: () => Promise<void>, done: string) => {
    setBusy(kind);
    try {
      await action();
      await fetchProjectDetails(workspaceSlug, projectId);
      setToast({ type: TOAST_TYPE.SUCCESS, title: done });
    } catch (e) {
      const api = (e as { response?: { data?: { error?: string } } })?.response?.data?.error;
      const msg = api ?? (e instanceof Error && e.message === "not-an-image" ? t("projlogo.not_image") : undefined);
      setToast({ type: TOAST_TYPE.ERROR, title: t("projlogo.error"), message: msg });
    } finally {
      setBusy(null);
    }
  };

  const onFile = (file: File | undefined) => {
    if (input.current) input.current.value = ""; // elegir el mismo archivo otra vez vuelve a disparar el cambio
    if (!file) return;
    void run(
      "upload",
      async () => {
        const { blob, name } = await squareLogo(file);
        await projectLogoService.upload(workspaceSlug, projectId, blob, name);
      },
      t("projlogo.saved")
    );
  };

  return (
    <section className="mb-6 flex items-center gap-4 rounded-lg border border-subtle p-4" data-mawesi="project-logo-upload">
      <span className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-layer-1">
        <Logo logo={logo} size={36} />
      </span>
      <div className="min-w-0 flex-1">
        <h3 className="text-14 font-medium text-primary">{t("projlogo.title")}</h3>
        <p className="text-13 text-secondary">{t("projlogo.help")}</p>
      </div>
      <input
        ref={input}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/svg+xml"
        className="hidden"
        onChange={(e) => onFile(e.target.files?.[0])}
      />
      <div className="flex shrink-0 gap-2">
        {hasImage && (
          <Button
            type="button"
            variant="secondary"
            size="lg"
            loading={busy === "remove"}
            disabled={!!busy}
            onClick={() => void run("remove", () => projectLogoService.remove(workspaceSlug, projectId), t("projlogo.removed"))}
          >
            {t("projlogo.remove")}
          </Button>
        )}
        <Button type="button" variant="primary" size="lg" loading={busy === "upload"} disabled={!!busy} onClick={() => input.current?.click()}>
          {hasImage ? t("projlogo.change") : t("projlogo.upload")}
        </Button>
      </div>
    </section>
  );
});
