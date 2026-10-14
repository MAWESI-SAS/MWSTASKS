/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Interruptor Sí/No propio (mismo aspecto que el ToggleSwitch de Plane, que desaparece en su próxima versión).
 */
type Props = { value: boolean; onChange: (v: boolean) => void; disabled?: boolean; label?: string };

export function Toggle({ value, onChange, disabled, label }: Props) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={value}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!value)}
      data-mawesi-input="checkbox"
      className={`relative inline-flex h-5 w-8 flex-shrink-0 cursor-pointer rounded-full border border-subtle transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-50 ${
        value ? "bg-accent-primary" : "bg-(--text-color-icon-placeholder)"
      }`}
    >
      <span
        className={`inline-block h-4 w-4 transform self-center rounded-full bg-(--text-color-icon-on-color) transition duration-200 ${
          value ? "translate-x-3" : "translate-x-0"
        }`}
      />
    </button>
  );
}
