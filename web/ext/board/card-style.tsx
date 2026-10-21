/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Marca invisible dentro de las propiedades de la tarjeta con el color que le toca. `card-style.css` pinta la tarjeta
 * entera con `:has()`, sin editar los componentes de Plane (tablero y lista).
 */
import { observer } from "mobx-react";
import { useParams } from "react-router";
import { useProjectState } from "../plane";
import { ruleFor } from "./card-rules";
import type { TCardIssue } from "./card-rules";
import { useBoardConfig } from "./use-board";

type Props = { projectId: string; issue: TCardIssue };

export const CardStyle = observer(function CardStyle({ projectId, issue }: Props) {
  const { workspaceSlug } = useParams();
  const config = useBoardConfig(workspaceSlug, projectId);
  const { getStateById } = useProjectState();
  if (!config?.card_rules.length) return null;
  const group = issue.state_id ? getStateById(issue.state_id)?.group : undefined;
  const rule = ruleFor(config.card_rules, issue, group === "completed" || group === "cancelled");
  if (!rule) return null;
  return <span hidden data-mawesi="card-style" data-color={rule.color} title={rule.name} />;
});
