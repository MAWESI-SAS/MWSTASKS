/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Confirmación (reemplaza AlertModalCore de Plane dentro de ext/, por el mismo motivo que MawesiModal).
 */
import type { ReactNode } from "react";
import { Button } from "../plane";
import { MODAL_WIDTH, MawesiModal } from "./modal";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  body: ReactNode;
  confirmText: string;
  confirmingText: string;
  cancelText: string;
  isSubmitting: boolean;
};

export function MawesiConfirm({ isOpen, onClose, onConfirm, title, body, confirmText, confirmingText, cancelText, isSubmitting }: Props) {
  return (
    <MawesiModal isOpen={isOpen} onClose={onClose} width={MODAL_WIDTH.LG}>
      <div className="px-5 py-4" data-mawesi="confirm">
        <h3 className="text-18 font-medium">{title}</h3>
        <p className="mt-3 text-13 text-secondary">{body}</p>
        <div className="mt-4 flex justify-end gap-2">
          <Button type="button" variant="secondary" size="lg" onClick={onClose}>
            {cancelText}
          </Button>
          <Button type="button" variant="error-fill" size="lg" onClick={onConfirm} loading={isSubmitting} data-mawesi="confirm-ok">
            {isSubmitting ? confirmingText : confirmText}
          </Button>
        </div>
      </div>
    </MawesiModal>
  );
}
