import React from "react";

const fmt = (n) => Number(n).toLocaleString("pt-BR");

/** Carbon composition bar: 8px, square segments, no radius, no vertical rule. */
export function RentabilityBar({ rentavel = 0, nao = 0, indeterminado = 0, showLegend = false, height = 8, masked = false }) {
  const total = (rentavel + nao + indeterminado) || 1;
  const pct = (n) => (n / total * 100) + "%";
  const seg = (w, c) => <i style={{ width: w, height: "100%", background: c, display: "block" }} />;
  const key = (c) => <i style={{ width: 8, height: 8, background: c, flex: "none" }} />;
  const item = (color, label, value) => (
    <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--muted)" }}>
      {key(color)}{label} <b style={{ fontFamily: "var(--mono)", fontWeight: 600, color: "var(--text)" }}>{fmt(value)}</b>
    </span>
  );
  return (
    <div>
      <div style={{ display: "flex", height, overflow: "hidden", background: "var(--ink-10)", borderRadius: 0 }}>
        {seg(pct(rentavel), "var(--green-50)")}
        {masked
          ? seg(pct(nao + indeterminado), "var(--ink-30)")
          : <>{seg(pct(nao), "var(--red-50)")}{seg(pct(indeterminado), "var(--amber-40)")}</>}
      </div>
      {showLegend && (
        <div style={{ display: "flex", gap: "6px 16px", marginTop: 10, flexWrap: "wrap" }}>
          {masked ? (
            <>
              {item("var(--green-50)", "Aproveitável", rentavel)}
              {item("var(--ink-30)", "Descarte", nao + indeterminado)}
            </>
          ) : (
            <>
              {item("var(--green-50)", "Rentável", rentavel)}
              {item("var(--red-50)", "Não rentável", nao)}
              {item("var(--amber-40)", "Indeterminado", indeterminado)}
            </>
          )}
        </div>
      )}
    </div>
  );
}
