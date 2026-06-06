function barColor(sig) {
  if (sig === "CHEAP") return "#3B6D11";
  if (sig === "RICH") return "#A32D2D";
  return "#B4B2A9";
}

function barBg(sig) {
  if (sig === "CHEAP") return "#EAF3DE";
  if (sig === "RICH") return "#FCEBEB";
  return "#F1EFE8";
}

export function MiniBar({ pct, sig, label }) {
  const color = barColor(sig);
  const bg = barBg(sig);
  return (
    <div style={{ marginBottom: 4 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
        <span style={{ fontSize: 9, color: "#aaa", letterSpacing: "0.03em" }}>{label}</span>
        <span style={{ fontSize: 9, fontWeight: 500, color }}>{pct}th</span>
      </div>
      <div style={{ height: 4, borderRadius: 2, background: bg, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 2 }} />
      </div>
    </div>
  );
}

export function CompositeBadge({ composite }) {
  let bg, color;
  if (composite.startsWith("CHEAP")) { bg = "#EAF3DE"; color = "#3B6D11"; }
  else if (composite.startsWith("RICH")) { bg = "#FCEBEB"; color = "#A32D2D"; }
  else { bg = "#F1EFE8"; color = "#5F5E5A"; }
  return (
    <span style={{ background: bg, color, fontSize: 10, fontWeight: 500, padding: "2px 6px", borderRadius: 4 }}>
      {composite}
    </span>
  );
}