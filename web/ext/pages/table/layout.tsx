/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { observer } from "mobx-react";
import { Outlet, useParams } from "react-router";
import { Table2 } from "lucide-react";
import { useT } from "../../i18n";
import { AppHeader, BreadcrumbLink, Breadcrumbs, ContentWrapper, Header, useProject } from "../../plane";

const TableHeader = observer(function TableHeader() {
  const t = useT();
  const { projectId = "" } = useParams();
  const { getPartialProjectById } = useProject();
  const project = getPartialProjectById(projectId);
  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs>
          <Breadcrumbs.Item component={<BreadcrumbLink label={project?.name ?? ""} />} />
          <Breadcrumbs.Item component={<BreadcrumbLink label={t("table.title")} icon={<Table2 className="size-4 text-secondary" />} />} />
        </Breadcrumbs>
      </Header.LeftItem>
    </Header>
  );
});

export default function TableLayout() {
  return (
    <>
      <AppHeader header={<TableHeader />} />
      <ContentWrapper>
        <Outlet />
      </ContentWrapper>
    </>
  );
}
