/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Ventana modal de ext/. Igual a ModalCore de Plane, pero con `data-prevent-outside-click` en TODA la capa
 * (fondo + contenido). Motivo: el peek de Plane se cierra con cualquier clic fuera de él
 * (hooks/use-peek-overview-outside-click.tsx), y el modal vive en un portal fuera del peek. Plane evita eso
 * en sus modales con banderas de su store (isAnyModalOpen), que no podemos ampliar sin editar Plane;
 * su detector sí respeta `data-prevent-outside-click`.
 */
import { Fragment } from "react";
import type { ReactNode } from "react";
import { Dialog, Transition } from "../plane";

/** Mismas clases que EModalWidth/EModalPosition de Plane (copiadas para no depender de ellas). */
export const MODAL_WIDTH = { MD: "sm:max-w-md", LG: "sm:max-w-lg" } as const;
const CENTER = "flex items-end sm:items-center justify-center p-4 min-h-full";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
  width?: (typeof MODAL_WIDTH)[keyof typeof MODAL_WIDTH];
};

export function MawesiModal({ isOpen, onClose, children, width = MODAL_WIDTH.MD }: Props) {
  return (
    <Transition.Root show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-30" onClose={onClose} data-prevent-outside-click="">
        <Transition.Child as={Fragment} enter="ease-out duration-300" enterFrom="opacity-0" enterTo="opacity-100" leave="ease-in duration-200" leaveFrom="opacity-100" leaveTo="opacity-0">
          <div className="fixed inset-0 bg-backdrop transition-opacity" />
        </Transition.Child>
        <div className="fixed inset-0 z-30 overflow-y-auto">
          <div className={CENTER}>
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
              enterTo="opacity-100 translate-y-0 sm:scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 translate-y-0 sm:scale-100"
              leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
            >
              <Dialog.Panel className={`relative w-full transform rounded-lg bg-surface-1 text-left shadow-raised-200 transition-all ${width}`}>
                {children}
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
}
