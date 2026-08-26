import React from "react";

const MAP = {
  rentavel:      { label: "Rentável",      bg: "var(--green-10)", fg: "var(--green-70)", dot: "var(--green-50)" },
  nao:           { label: "Não rentável",  bg: "var(--red-10)",   fg: "var(--red-70)",   dot: "var(--red-60)" },
  indeterminado: { label: "Indeterminado", bg: "var(--amber-10)", fg: "var(--amber-70)", dot: "var(--amber-60)" }
};

/** Carbon status tag: 0px corners, 11px/800 label, 6px square marker. */
export function VerdictPill({ verdict = "rentavel", showDot = true, children }) {
  const m = MAP[verdict] || MAP.rentavel;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 800,
      letterSpacing: ".03em", padding: "3px 9px", borderRadius: 0,
      background: m.bg, color: m.fg, whiteSpace: "nowrap", fontFamily: "var(--sans)"
    }}>
      {showDot && <span style={{ width: 6, height: 6, background: m.dot, flex: "none" }} />}
      {children || m.label}
    </span>
  );
}
