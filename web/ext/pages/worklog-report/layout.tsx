/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { Outlet } from "react-router";
import { Clock } from "lucide-react";
import { useT } from "../../i18n";
import { AppHeader, BreadcrumbLink, Breadcrumbs, ContentWrapper, Header } from "../../plane";

function ReportHeader() {
  const t = useT();
  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs>
          <Breadcrumbs.Item component={<BreadcrumbLink label={t("report.title")} icon={<Clock className="size-4 text-secondary" />} />} />
        </Breadcrumbs>
      </Header.LeftItem>
    </Header>
  );
}

export default function WorklogReportLayout() {
  return (
    <>
      <AppHeader header={<ReportHeader />} />
      <ContentWrapper>
        <Outlet />
      </ContentWrapper>
    </>
  );
}
