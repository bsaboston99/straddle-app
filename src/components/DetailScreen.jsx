import { tickers } from "../data/tickers";
import { MiniBar, CompositeBadge } from "./MiniBar";
import TabBar from "./TabBar";

const upColor = "#3B6D11", downColor = "#A32D2D";
const upBg = "#EAF3DE", downBg = "#FCEBEB";

function Sparkline({ up }) {
  const pts = up
    ? "0,55 30,48 60,52 90,40 120,38 160,30 200,25 240,28 280,18 320,14 350,8"
    : "0,10 30,18 60,14 90,26 120,30 160,38 200,42 240,36 280,48 320,52 350,60";
  return (
    <svg viewBox="0 0 350 68" preserveAspectRatio="none" style={{ width: "100%", height: 68 }}>
      <polyline
        points={pts}
        fill="none"
        stroke={up ? upColor : downColor}
        strokeWidth="1.8"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default function DetailScreen({ sym, onBack, onTab }) {
  const t = tickers[sym];
  const isUp = t.dir === "up";

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, fontFamily: "system-ui, sans-serif" }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "16px 20px 14px", borderBottom: "0.5px solid #e5e5e5" }}>
        <button
          onClick={onBack}
          style={{ background: "none", border: "none", cursor: "pointer", fontSize: 22, color: "#888", padding: 0 }}
        >
          &#8592;
        </button>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 18, fontWeight: 500 }}>{sym}</div>
          <div style={{ fontSize: 12, color: "#888", marginTop: 1 }}>{t.name}</div>
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, padding: "20px", overflowY: "auto" }}>

        {/* Price hero */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 32, fontWeight: 500 }}>{t.price}</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
            <span style={{
              background: isUp ? upBg : downBg,
              color: isUp ? upColor : downColor,
              fontSize: 13, fontWeight: 500, padding: "3px 8px", borderRadius: 5
            }}>
              {t.change}
            </span>
            <span style={{ fontSize: 12, color: "#888" }}>{t.earnInfo}</span>
          </div>
        </div>

        {/* Sparkline */}
        <Sparkline up={isUp} />

        {/* Straddle percentiles */}
        <div style={{ fontSize: 11, fontWeight: 500, color: "#888", letterSpacing: "0.04em", textTransform: "uppercase", margin: "20px 0 8px" }}>
          Straddle percentiles
        </div>
        <div style={{ background: "#f7f7f5", borderRadius: 8, padding: "14px 16px" }}>
          <div style={{ marginBottom: 12 }}>
            <MiniBar pct={t.pct_a} sig={t.sig_a} label="Front-month vs SPY (overall vol)" />
            <div style={{ fontSize: 11, color: "#888", marginTop: 2 }}>{t.adj_a}</div>
          </div>
          <div style={{ marginBottom: 12 }}>
            <MiniBar pct={t.pct_b} sig={t.sig_b} label="Back-month vs SPY (background vol)" />
            <div style={{ fontSize: 11, color: "#888", marginTop: 2 }}>{t.adj_b}</div>
          </div>
          <div style={{ marginBottom: 4 }}>
            <MiniBar pct={t.pct_ep} sig={t.sig_ep} label="Earnings premium (event fear)" />
            <div style={{ fontSize: 11, color: "#888", marginTop: 2 }}>{t.adj_ep}</div>
          </div>
          <div style={{ marginTop: 14, paddingTop: 12, borderTop: "0.5px solid #eee" }}>
            <span style={{ fontSize: 11, color: "#888", marginRight: 8 }}>Composite:</span>
            <CompositeBadge composite={t.composite} />
          </div>
        </div>

        {/* Straddle values */}
        <div style={{ fontSize: 11, fontWeight: 500, color: "#888", letterSpacing: "0.04em", textTransform: "uppercase", margin: "20px 0 10px" }}>
          Straddle values
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          {[
            { label: "Front-month straddle", val: t.front, sub: t.frontPct },
            { label: "Back-month straddle", val: t.back, sub: t.backPct },
            { label: "Earnings premium ratio", val: t.epr, sub: "vs SPY baseline" },
            { label: "SPY-normalized move", val: t.spyNorm, sub: "implied vs benchmark" },
          ].map(m => (
            <div key={m.label} style={{ background: "#f7f7f5", borderRadius: 8, padding: 12 }}>
              <div style={{ fontSize: 11, color: "#888", marginBottom: 4 }}>{m.label}</div>
              <div style={{ fontSize: 18, fontWeight: 500 }}>{m.val}</div>
              <div style={{ fontSize: 11, color: "#888", marginTop: 2 }}>{m.sub}</div>
            </div>
          ))}
        </div>

        {/* Key details */}
        <div style={{ fontSize: 11, fontWeight: 500, color: "#888", letterSpacing: "0.04em", textTransform: "uppercase", margin: "20px 0 10px" }}>
          Key details
        </div>
        {[
          { label: "Earnings date", val: t.earnDate },
          { label: "52-week range", val: t.wk52 },
          { label: "Implied volatility", val: t.iv },
          { label: "IV rank", val: t.ivr },
          { label: "Historical move avg", val: t.hist },
        ].map(r => (
          <div key={r.label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0", borderBottom: "0.5px solid #eee" }}>
            <span style={{ fontSize: 13, color: "#666" }}>{r.label}</span>
            <span style={{ fontSize: 13, fontWeight: 500 }}>{r.val}</span>
          </div>
        ))}

        {/* Signal card */}
        <div style={{
          background: t.signal.type === "warn" ? "#FAEEDA" : "#EAF3DE",
          borderRadius: 8, padding: "12px 14px", marginTop: 16, marginBottom: 8
        }}>
          <div style={{ fontSize: 11, fontWeight: 500, color: t.signal.type === "warn" ? "#854F0B" : "#3B6D11", marginBottom: 2 }}>
            {t.signal.label}
          </div>
          <div style={{ fontSize: 13, color: t.signal.type === "warn" ? "#633806" : "#27500A" }}>
            {t.signal.text}
          </div>
        </div>

      </div>

      <TabBar active="Watchlist" onTab={onTab} />
    </div>
  );
}