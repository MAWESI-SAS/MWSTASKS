/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Cuando el servidor frena un cambio por una dependencia (409 "dependency_blocked") o una relación que cierra un círculo
 * (400 "dependency_cycle"), Plane deshace el cambio pero muestra un error genérico (o ninguno). Esto escucha las
 * respuestas de XMLHttpRequest (axios, que usa Plane) y muestra el motivo real. No cambia ningún pedido.
 */
import { TOAST_TYPE, setToast } from "../plane";

const KINDS = new Set(["dependency_blocked", "dependency_cycle"]);
let installed = false;

export const installDependencyToast = (title: () => string) => {
  if (installed || typeof XMLHttpRequest === "undefined") return;
  installed = true;
  const send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function patchedSend(this: XMLHttpRequest, ...args: Parameters<XMLHttpRequest["send"]>) {
    this.addEventListener("load", () => {
      if (this.status !== 409 && this.status !== 400) return;
      try {
        const body = typeof this.response === "string" ? JSON.parse(this.response) : this.response;
        if (body && KINDS.has(body.mawesi)) setToast({ type: TOAST_TYPE.ERROR, title: title(), message: body.error });
      } catch {
        // respuesta que no es JSON: no es nuestra
      }
    });
    return send.apply(this, args);
  };
};
