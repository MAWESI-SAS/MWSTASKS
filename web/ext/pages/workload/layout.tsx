/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { Outlet } from "react-router";
import { Users } from "lucide-react";
import { useT } from "../../i18n";
import { AppHeader, BreadcrumbLink, Breadcrumbs, ContentWrapper, Header } from "../../plane";

function WorkloadHeader() {
  const t = useT();
  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs>
          <Breadcrumbs.Item component={<BreadcrumbLink label={t("workload.title")} icon={<Users className="size-4 text-secondary" />} />} />
        </Breadcrumbs>
      </Header.LeftItem>
    </Header>
  );
}

export default function WorkloadLayout() {
  return (
    <>
      <AppHeader header={<WorkloadHeader />} />
      <ContentWrapper>
        <Outlet />
      </ContentWrapper>
    </>
  );
}
