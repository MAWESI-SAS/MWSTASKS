/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Configuración > General del proyecto: bloque "Logo con imagen" arriba del formulario de Plane.
 * El formulario de Plane guarda una copia de `logo_props` al montarse y la manda entera al guardar: se vuelve a
 * montar (key) cuando cambia la imagen, para que "Update project" no borre un logo recién subido.
 */
import { observer } from "mobx-react";
import { ProjectDetailsForm as Upstream } from "@upstream/components/project/form";
import type { IProjectDetailsForm } from "@upstream/components/project/form";
import { useProject } from "../../plane";
import { logoImageUrl } from "../../projects/logo";
import { ProjectLogoUpload } from "../../projects/logo-upload";

export * from "@upstream/components/project/form";

export const ProjectDetailsForm = observer(function ProjectDetailsForm(props: IProjectDetailsForm) {
  const { getProjectById } = useProject();
  const project = getProjectById(props.projectId) ?? props.project;
  return (
    <>
      {props.isAdmin && (
        <ProjectLogoUpload workspaceSlug={props.workspaceSlug} projectId={props.projectId} logo={project.logo_props} />
      )}
      <Upstream key={logoImageUrl(project.logo_props) ?? "sin-imagen"} {...props} project={project} />
    </>
  );
});
