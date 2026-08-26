import React from "react";

/* Carbon: cantos 0px, borda de 2px nas variantes de contorno ($button-border-width), altura vinda
   dos tokens de controle (--ctl-*) — todos sobre degraus da escada —, rótulo que NÃO cresce com a
   altura. Antes daqui saíam cantos arredondados (--r-sm/--r-md) e alturas 36/44/52 — nenhuma das
   duas últimas existe na escala do sistema (36 / 48 / 56). */
const SIZES = {
  sm: { height: "var(--ctl-sm)", padding: "0 12px", fontSize: 13 },
  md: { height: "var(--ctl-md)", padding: "0 16px", fontSize: 14 },
  lg: { height: "var(--ctl-lg)", padding: "0 16px", fontSize: 14 }
};
const VARIANTS = {
  primary: { background: "var(--blue-60)", color: "#fff", border: "2px solid transparent" },
  ghost:   { background: "transparent", color: "var(--text)", border: "2px solid var(--line-2)" },
  danger:  { background: "transparent", color: "var(--red-60)", border: "2px solid var(--red-60)" },
  success: { background: "transparent", color: "var(--green-60)", border: "2px solid var(--green-50)" }
};

/** WhatTheChip action button. Blue = primary action across the whole system. */
export function Button({ variant = "primary", size = "md", iconLeft = null, disabled = false, children, style = {}, ...rest }) {
  const s = SIZES[size] || SIZES.md;
  const v = VARIANTS[variant] || VARIANTS.primary;
  return (
    <button disabled={disabled} style={{
      display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8,
      height: s.height, padding: s.padding, fontSize: s.fontSize, fontWeight: 600,
      fontFamily: "var(--sans)", borderRadius: 0, whiteSpace: "nowrap",
      cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.5 : 1,
      transition: "background var(--dur-1), border-color var(--dur-1)",
      ...v, ...style
    }} {...rest}>
      {iconLeft}{children}
    </button>
  );
}
