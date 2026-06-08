export function MiniBar({ pct, sig, label }) {
  const color = sig === "CHEAP" ? "var(--up)"      : sig === "RICH" ? "var(--down)"      : "var(--text3)";
  const bg    = sig === "CHEAP" ? "var(--up-bg)"   : sig === "RICH" ? "var(--down-bg)"   : "var(--border)";
  return (
    <div style={{ marginBottom: 4 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
        <span style={{ fontSize: 9, color: "var(--text3)", letterSpacing: "0.03em" }}>{label}</span>
        <span style={{ fontSize: 9, fontWeight: 500, color }}>{pct}th</span>
      </div>
      <div style={{ height: 4, borderRadius: 2, background: bg, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 2 }} />
      </div>
    </div>
  );
}

export function CompositeBadge({ composite }) {
  const bg    = composite.startsWith("CHEAP") ? "var(--up-bg)"   : composite.startsWith("RICH") ? "var(--down-bg)"  : "var(--border)";
  const color = composite.startsWith("CHEAP") ? "var(--up)"      : composite.startsWith("RICH") ? "var(--down)"     : "var(--text2)";
  return (
    <span style={{ background: bg, color, fontSize: 10, fontWeight: 500, padding: "2px 6px", borderRadius: 4 }}>
      {composite}
    </span>
  );
}
