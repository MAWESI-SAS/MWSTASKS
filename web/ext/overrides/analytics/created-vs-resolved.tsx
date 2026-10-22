/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Analytics → "Created vs Resolved". Copia del de Plane con un cambio: las dos curvas van superpuestas, no apiladas.
 * Plane les pone el mismo stackId, así la curva "Created" se dibuja encima de "Resolved" y parece el doble
 * (septiembre 2022: 301 creadas y 301 resueltas se veían como 602). Los datos los arma backend views/analytics.py.
 */
import { useMemo } from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import useSWR from "swr";
import {
  AnalyticsSectionWrapper, AnalyticsService, AreaChart, ChartLoader, EmptyStateCompact, renderFormattedDate, useAnalytics,
  useTranslation,
} from "../../plane";
import type { IChartResponse, TChartData } from "../../plane";

const analyticsService = new AnalyticsService();

const AREA = { fillOpacity: 1, showDot: false, smoothCurves: true, strokeOpacity: 1 };

const CreatedVsResolved = observer(function CreatedVsResolved() {
  const { selectedDuration, selectedDurationLabel, selectedProjects, selectedCycle, selectedModule, isPeekView, isEpic } = useAnalytics();
  const { workspaceSlug = "" } = useParams();
  const { t } = useTranslation();
  const { data, isLoading } = useSWR(
    `created-vs-resolved-${workspaceSlug}-${selectedDuration}-${selectedProjects}-${selectedCycle}-${selectedModule}-${isPeekView}-${isEpic}`,
    () =>
      analyticsService.getAdvanceAnalyticsCharts<IChartResponse>(
        workspaceSlug,
        "work-items",
        {
          ...(selectedProjects?.length > 0 && { project_ids: selectedProjects?.join(",") }),
          ...(selectedCycle ? { cycle_id: selectedCycle } : {}),
          ...(selectedModule ? { module_id: selectedModule } : {}),
          ...(isEpic ? { epic: true } : {}),
        },
        isPeekView
      )
  );
  const parsedData: TChartData<string, string>[] = useMemo(() => {
    if (!data?.data) return [];
    return data.data.map((datum) => ({ ...datum, [datum.key]: datum.count, name: renderFormattedDate(datum.key) ?? datum.key }));
  }, [data]);

  // Un stackId distinto por curva = no se apilan: cada una muestra su propio número.
  const areas = useMemo(
    () => [
      { ...AREA, key: "created_issues", stackId: "created", label: "Created", fill: "#1192E81f", strokeColor: "#1192E8" },
      { ...AREA, key: "completed_issues", stackId: "resolved", label: "Resolved", fill: "#1980381f", strokeColor: "#198038" },
    ],
    []
  );

  return (
    <AnalyticsSectionWrapper title={t("workspace_analytics.created_vs_resolved")} subtitle={selectedDurationLabel} className="col-span-1">
      {isLoading ? (
        <ChartLoader />
      ) : parsedData.length > 0 ? (
        <div data-mawesi="created-vs-resolved" className="contents">
          <AreaChart
            className="h-[350px] w-full"
            data={parsedData}
            areas={areas}
            xAxis={{ key: "name", label: t("date") }}
            yAxis={{
              key: "count",
              label: t("common.no_of", { entity: isEpic ? t("common.epics") : t("work_items") }),
              offset: -60,
              dx: -24,
            }}
            legend={{
              align: "left",
              verticalAlign: "bottom",
              layout: "horizontal",
              wrapperStyles: { justifyContent: "start", alignContent: "start", paddingLeft: "40px", paddingTop: "10px" },
            }}
          />
        </div>
      ) : (
        <EmptyStateCompact
          assetKey="unknown"
          assetClassName="size-20"
          rootClassName="border border-subtle px-5 py-10 md:py-20 md:px-20"
          title={t("workspace_empty_state.analytics_work_items.title")}
        />
      )}
    </AnalyticsSectionWrapper>
  );
});

export default CreatedVsResolved;
