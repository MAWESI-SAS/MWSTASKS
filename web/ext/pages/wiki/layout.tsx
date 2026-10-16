/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 */
import { Outlet } from "react-router";
import { BookOpen } from "lucide-react";
import { useT } from "../../i18n";
import { AppHeader, BreadcrumbLink, Breadcrumbs, ContentWrapper, Header } from "../../plane";

function WikiHeader() {
  const t = useT();
  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs>
          <Breadcrumbs.Item component={<BreadcrumbLink label={t("wiki.title")} icon={<BookOpen className="size-4 text-secondary" />} />} />
        </Breadcrumbs>
      </Header.LeftItem>
    </Header>
  );
}

export default function WikiLayout() {
  return (
    <>
      <AppHeader header={<WikiHeader />} />
      <ContentWrapper>
        <Outlet />
      </ContentWrapper>
    </>
  );
}
