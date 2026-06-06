import { tickers } from "../data/tickers";
import { MiniBar } from "./MiniBar";
import TabBar from "./TabBar";

const upColor = "#3B6D11", downColor = "#A32D2D";
const upBg = "#EAF3DE", downBg = "#FCEBEB";

function TickerRow({ sym, onClick }) {
  const t = tickers[sym];
  const isUp = t.dir === "up";
  return (
    <div
      onClick={onClick}
      style={{
        display: "grid", gridTemplateColumns: "1fr 70px 64px 80px",
        alignItems: "center", padding: "11px 16px", gap: 6,
        borderBottom: "0.5px solid #eee", cursor: "pointer"
      }}
    >
      <div>
        <div style={{ fontSize: 15, fontWeight: 500 }}>
          {sym}
          {t.earnBadge && (
            <span style={{ background: "#FAEEDA", color: "#854F0B", fontSize: 10, padding: "1px 5px", borderRadius: 4, marginLeft: 4, fontWeight: 500 }}>
              {t.earnBadge}
            </span>
          )}
        </div>
        <div style={{ fontSize: 11, color: "#aaa", marginTop: 2 }}>{t.earnSub}</div>
        <div style={{ marginTop: 6, width: 90 }}>
          <MiniBar pct={t.pct_a} sig={t.sig_a} label="A" />
          <MiniBar pct={t.pct_b} sig={t.sig_b} label="B" />
          <MiniBar pct={t.pct_ep} sig={t.sig_ep} label="EP" />
        </div>
      </div>
      <div style={{ textAlign: "right", fontSize: 13, fontWeight: 500 }}>{t.price}</div>
      <div style={{ textAlign: "right" }}>
        <span style={{
          background: isUp ? upBg : downBg,
          color: isUp ? upColor : downColor,
          fontSize: 11, fontWeight: 500, padding: "2px 5px", borderRadius: 4
        }}>
          {t.change}
        </span>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ fontSize: 13, fontWeight: 500 }}>{t.front}</div>
        <div style={{ fontSize: 10, color: "#aaa", marginTop: 1 }}>{t.frontPct}</div>
      </div>
    </div>
  );
}

export default function WatchlistScreen({ onSelectTicker, onTab }) {
  const thisWeek = ["NVDA", "ORCL", "ADBE"];
  const upcoming = ["TSLA", "AMZN", "META", "SPY"];

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, fontFamily: "system-ui, sans-serif" }}>

      <div style={{ padding: "18px 20px 12px", borderBottom: "0.5px solid #eee" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <h1 style={{ fontSize: 20, fontWeight: 500, margin: 0 }}>Watchlist</h1>
          <div style={{ display: "flex", gap: 16, fontSize: 20, color: "#888" }}>
            <span>🔔</span><span>🔍</span>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, background: "#f5f5f3", borderRadius: 8, padding: "8px 12px" }}>
          <span style={{ color: "#aaa", fontSize: 14 }}>🔍</span>
          <span style={{ fontSize: 14, color: "#aaa" }}>Search tickers...</span>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 70px 64px 80px", padding: "8px 16px 6px", gap: 6 }}>
        {["Ticker / Percentiles", "Price", "Chg", "Straddle"].map((h, i) => (
          <span key={h} style={{ fontSize: 10, color: "#aaa", textTransform: "uppercase", letterSpacing: "0.04em", textAlign: i > 0 ? "right" : "left" }}>
            {h}
          </span>
        ))}
      </div>

      <div style={{ flex: 1 }}>
        <div style={{ padding: "10px 16px 4px", fontSize: 12, fontWeight: 500, color: "#888" }}>Earnings this week</div>
        {thisWeek.map(sym => <TickerRow key={sym} sym={sym} onClick={() => onSelectTicker(sym)} />)}
        <div style={{ padding: "10px 16px 4px", fontSize: 12, fontWeight: 500, color: "#888" }}>Upcoming earnings</div>
        {upcoming.map(sym => <TickerRow key={sym} sym={sym} onClick={() => onSelectTicker(sym)} />)}
      </div>

      <TabBar active="Watchlist" onTab={onTab} />
    </div>
  );
}