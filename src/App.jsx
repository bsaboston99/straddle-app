import { useState } from "react";

const tickers = {
  NVDA: {
    name: "NVIDIA Corporation", price: "$924.60", change: "+2.14%", dir: "up",
    earnInfo: "Earnings Jun 9 — 3 days away", earnDate: "Jun 9, 2026 (3 days)",
    front: "$48.30", frontPct: "5.22% of price",
    back: "$61.80", backPct: "6.69% of price",
    epr: "2.51x", spyNorm: "+3.14%",
    wk52: "$462.00 – $974.00", iv: "62.4%", ivr: "78 / 100", hist: "±4.8% avg",
    earnBadge: "Jun 9", earnSub: "Earnings in 3 days",
    pct_a: 82, pct_b: 74, pct_ep: 21,
    sig_a: "RICH", sig_b: "NORMAL", sig_ep: "CHEAP",
    adj_a: "RICH (stock-specific)", adj_b: "NORMAL", adj_ep: "CHEAP (stock-specific)",
    composite: "MIXED / NORMAL",
    signal: { type: "green", label: "Elevated premium signal", text: "Front/back ratio suggests market pricing in outsized move. EPR above 2.0x historically favors straddle sellers post-earnings." }
  },
  ORCL: {
    name: "Oracle Corporation", price: "$137.45", change: "-0.87%", dir: "down",
    earnInfo: "Earnings Jun 10 — 4 days away", earnDate: "Jun 10, 2026 (4 days)",
    front: "$9.15", frontPct: "6.66% of price",
    back: "$11.40", backPct: "8.29% of price",
    epr: "3.20x", spyNorm: "+4.58%",
    wk52: "$98.40 – $163.00", iv: "71.2%", ivr: "85 / 100", hist: "±5.2% avg",
    earnBadge: "Jun 10", earnSub: "Earnings in 4 days",
    pct_a: 91, pct_b: 88, pct_ep: 78,
    sig_a: "RICH", sig_b: "RICH", sig_ep: "RICH",
    adj_a: "RICH (market-driven)", adj_b: "RICH (market-driven)", adj_ep: "RICH (stock-specific)",
    composite: "RICH (3/3 metrics)",
    signal: { type: "warn", label: "High EPR — elevated risk", text: "EPR of 3.20x is well above historical median. Back-month premium is 24% wider than front, suggesting uncertainty extending beyond this cycle." }
  },
  ADBE: {
    name: "Adobe Inc.", price: "$488.20", change: "+0.53%", dir: "up",
    earnInfo: "Earnings Jun 12 — 6 days away", earnDate: "Jun 12, 2026 (6 days)",
    front: "$27.40", frontPct: "5.61% of price",
    back: "$34.10", backPct: "6.98% of price",
    epr: "2.70x", spyNorm: "+3.53%",
    wk52: "$380.00 – $638.00", iv: "58.8%", ivr: "71 / 100", hist: "±4.6% avg",
    earnBadge: "Jun 12", earnSub: "Earnings in 6 days",
    pct_a: 58, pct_b: 52, pct_ep: 44,
    sig_a: "NORMAL", sig_b: "NORMAL", sig_ep: "NORMAL",
    adj_a: "NORMAL", adj_b: "NORMAL", adj_ep: "NORMAL",
    composite: "MIXED / NORMAL",
    signal: { type: "green", label: "Within historical range", text: "Implied move of 5.61% aligns closely with the ±4.6% historical average. Moderate EPR suggests fair pricing ahead of earnings." }
  },
  TSLA: {
    name: "Tesla, Inc.", price: "$182.30", change: "-1.44%", dir: "down",
    earnInfo: "Earnings Jul 17", earnDate: "Jul 17, 2026",
    front: "$18.75", frontPct: "10.28% of price",
    back: "$23.50", backPct: "12.89% of price",
    epr: "4.94x", spyNorm: "+8.20%",
    wk52: "$138.80 – $299.00", iv: "84.3%", ivr: "91 / 100", hist: "±8.1% avg",
    earnBadge: null, earnSub: "Jul 17",
    pct_a: 18, pct_b: 22, pct_ep: 12,
    sig_a: "CHEAP", sig_b: "CHEAP", sig_ep: "CHEAP",
    adj_a: "CHEAP (stock-specific)", adj_b: "CHEAP (stock-specific)", adj_ep: "CHEAP (stock-specific)",
    composite: "CHEAP (3/3 metrics)",
    signal: { type: "warn", label: "Very high EPR — extreme premium", text: "EPR of 4.94x is in the top decile historically. IV rank of 91 suggests options are expensive relative to the past year." }
  },
  AMZN: {
    name: "Amazon.com, Inc.", price: "$186.55", change: "+0.91%", dir: "up",
    earnInfo: "Earnings Jul 31", earnDate: "Jul 31, 2026",
    front: "$12.60", frontPct: "6.75% of price",
    back: "$15.90", backPct: "8.52% of price",
    epr: "3.25x", spyNorm: "+4.67%",
    wk52: "$151.00 – $242.00", iv: "45.1%", ivr: "62 / 100", hist: "±5.0% avg",
    earnBadge: null, earnSub: "Jul 31",
    pct_a: 34, pct_b: 41, pct_ep: 29,
    sig_a: "NORMAL", sig_b: "NORMAL", sig_ep: "CHEAP",
    adj_a: "NORMAL", adj_b: "NORMAL", adj_ep: "CHEAP (stock-specific)",
    composite: "MIXED / NORMAL",
    signal: { type: "green", label: "Moderate signal", text: "Implied move of 6.75% slightly above ±5.0% historical avg. EPR is elevated but IV rank is mid-range." }
  },
  META: {
    name: "Meta Platforms, Inc.", price: "$504.10", change: "+1.22%", dir: "up",
    earnInfo: "Earnings Jul 30", earnDate: "Jul 30, 2026",
    front: "$29.85", frontPct: "5.92% of price",
    back: "$37.20", backPct: "7.38% of price",
    epr: "2.85x", spyNorm: "+3.84%",
    wk52: "$414.00 – $612.00", iv: "51.6%", ivr: "68 / 100", hist: "±5.3% avg",
    earnBadge: null, earnSub: "Jul 30",
    pct_a: 61, pct_b: 55, pct_ep: 48,
    sig_a: "NORMAL", sig_b: "NORMAL", sig_ep: "NORMAL",
    adj_a: "NORMAL", adj_b: "NORMAL", adj_ep: "NORMAL",
    composite: "MIXED / NORMAL",
    signal: { type: "green", label: "Near fair value", text: "Implied move close to historical average. EPR of 2.85x is moderate. Balanced setup." }
  },
  SPY: {
    name: "SPDR S&P 500 ETF (Benchmark)", price: "$537.80", change: "+0.34%", dir: "up",
    earnInfo: "SPY benchmark — no earnings", earnDate: "N/A (ETF)",
    front: "$11.20", frontPct: "2.08% of price",
    back: "$14.60", backPct: "2.71% of price",
    epr: "1.00x", spyNorm: "Baseline",
    wk52: "$472.00 – $613.00", iv: "14.2%", ivr: "42 / 100", hist: "±1.2% avg",
    earnBadge: null, earnSub: "Benchmark",
    pct_a: 50, pct_b: 48, pct_ep: 50,
    sig_a: "NORMAL", sig_b: "NORMAL", sig_ep: "NORMAL",
    adj_a: "NORMAL", adj_b: "NORMAL", adj_ep: "NORMAL",
    composite: "MIXED / NORMAL",
    signal: { type: "green", label: "Benchmark reference", text: "All straddle values and EPR ratios are normalized against SPY. Current front-month straddle of 2.08% reflects low broad-market volatility." }
  }
};

const upColor = "#3B6D11";
const downColor = "#A32D2D";
const upBg = "#EAF3DE";
const downBg = "#FCEBEB";

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

function MiniBar({ pct, sig, label }) {
  const color = barColor(sig);
  const bg = barBg(sig);
  return (
    <div style={{ marginBottom: 4 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
        <span style={{ fontSize: 9, color: "#aaa", letterSpacing: "0.03em" }}>{label}</span>
        <span style={{ fontSize: 9, fontWeight: 500, color }}>{pct}th</span>
      </div>
      <div style={{ height: 4, borderRadius: 2, background: bg, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 2, transition: "width 0.4s ease" }} />
      </div>
    </div>
  );
}

function CompositeBadge({ composite }) {
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

function Sparkline({ up }) {
  const pts = up
    ? "0,55 30,48 60,52 90,40 120,38 160,30 200,25 240,28 280,18 320,14 350,8"
    : "0,10 30,18 60,14 90,26 120,30 160,38 200,42 240,36 280,48 320,52 350,60";
  const color = up ? upColor : downColor;
  return (
    <svg viewBox="0 0 350 68" preserveAspectRatio="none" style={{ width: "100%", height: 68 }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

function DetailScreen({ sym, onBack }) {
  const t = tickers[sym];
  const isUp = t.dir === "up";
  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, fontFamily: "system-ui, sans-serif" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "16px 20px 14px", borderBottom: "0.5px solid #e5e5e5" }}>
        <button onClick={onBack} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 22, color: "#888", padding: 0 }}>&#8592;</button>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 18, fontWeight: 500 }}>{sym}</div>
          <div style={{ fontSize: 12, color: "#888", marginTop: 1 }}>{t.name}</div>
        </div>
      </div>

      <div style={{ flex: 1, padding: "20px", overflowY: "auto" }}>
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 32, fontWeight: 500 }}>{t.price}</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
            <span style={{ background: isUp ? upBg : downBg, color: isUp ? upColor : downColor, fontSize: 13, fontWeight: 500, padding: "3px 8px", borderRadius: 5 }}>{t.change}</span>
            <span style={{ fontSize: 12, color: "#888" }}>{t.earnInfo}</span>
          </div>
        </div>

        <Sparkline up={isUp} />

        <div style={{ fontSize: 11, fontWeight: 500, color: "#888", letterSpacing: "0.04em", textTransform: "uppercase", margin: "20px 0 8px" }}>Straddle percentiles</div>
        <div style={{ background: "#f7f7f5", borderRadius: 8, padding: "14px 16px", marginBottom: 4 }}>
          <div style={{ marginBottom: 12 }}>
            <MiniBar pct={t.pct_a} sig={t.sig_a} label="Front-month vs SPY (overall vol)" />
            <div style={{ fontSize: 11, color: "#888", marginTop: 2, paddingLeft: 0 }}>{t.adj_a}</div>
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

        <div style={{ fontSize: 11, fontWeight: 500, color: "#888", letterSpacing: "0.04em", textTransform: "uppercase", margin: "20px 0 10px" }}>Straddle values</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 4 }}>
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

        <div style={{ fontSize: 11, fontWeight: 500, color: "#888", letterSpacing: "0.04em", textTransform: "uppercase", margin: "20px 0 10px" }}>Key details</div>
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

        <div style={{ background: t.signal.type === "warn" ? "#FAEEDA" : "#EAF3DE", borderRadius: 8, padding: "12px 14px", marginTop: 16, marginBottom: 8 }}>
          <div style={{ fontSize: 11, fontWeight: 500, color: t.signal.type === "warn" ? "#854F0B" : "#3B6D11", marginBottom: 2 }}>{t.signal.label}</div>
          <div style={{ fontSize: 13, color: t.signal.type === "warn" ? "#633806" : "#27500A" }}>{t.signal.text}</div>
        </div>
      </div>

      <div style={{ display: "flex", borderTop: "0.5px solid #eee" }}>
        {[["☰", "Watchlist"], ["📊", "Analysis"], ["📅", "Earnings"], ["⚙️", "Settings"]].map(([icon, label]) => (
          <div key={label} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", padding: "10px 0 12px", gap: 4, cursor: "pointer", color: "#aaa", fontSize: 10 }}>
            <span style={{ fontSize: 20 }}>{icon}</span>
            <span>{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TickerRow({ sym, onClick }) {
  const t = tickers[sym];
  const isUp = t.dir === "up";
  return (
    <div onClick={onClick} style={{ display: "grid", gridTemplateColumns: "1fr 70px 64px 80px", alignItems: "center", padding: "11px 16px", gap: 6, borderBottom: "0.5px solid #eee", cursor: "pointer" }}>
      <div>
        <div style={{ fontSize: 15, fontWeight: 500 }}>
          {sym}
          {t.earnBadge && <span style={{ background: "#FAEEDA", color: "#854F0B", fontSize: 10, padding: "1px 5px", borderRadius: 4, marginLeft: 4, fontWeight: 500 }}>{t.earnBadge}</span>}
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
        <span style={{ background: isUp ? upBg : downBg, color: isUp ? upColor : downColor, fontSize: 11, fontWeight: 500, padding: "2px 5px", borderRadius: 4 }}>{t.change}</span>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ fontSize: 13, fontWeight: 500 }}>{t.front}</div>
        <div style={{ fontSize: 10, color: "#aaa", marginTop: 1 }}>{t.frontPct}</div>
      </div>
    </div>
  );
}

export default function App() {
  const [selected, setSelected] = useState(null);
  const thisWeek = ["NVDA", "ORCL", "ADBE"];
  const upcoming = ["TSLA", "AMZN", "META", "SPY"];

  if (selected) return <DetailScreen sym={selected} onBack={() => setSelected(null)} />;

  return (
    <div style={{ maxWidth: 390, margin: "0 auto", minHeight: "100vh", display: "flex", flexDirection: "column", fontFamily: "system-ui, sans-serif", borderLeft: "0.5px solid #eee", borderRight: "0.5px solid #eee" }}>
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
          <span key={h} style={{ fontSize: 10, color: "#aaa", textTransform: "uppercase", letterSpacing: "0.04em", textAlign: i > 0 ? "right" : "left" }}>{h}</span>
        ))}
      </div>

      <div style={{ flex: 1 }}>
        <div style={{ padding: "10px 16px 4px", fontSize: 12, fontWeight: 500, color: "#888" }}>Earnings this week</div>
        {thisWeek.map(sym => <TickerRow key={sym} sym={sym} onClick={() => setSelected(sym)} />)}
        <div style={{ padding: "10px 16px 4px", fontSize: 12, fontWeight: 500, color: "#888" }}>Upcoming earnings</div>
        {upcoming.map(sym => <TickerRow key={sym} sym={sym} onClick={() => setSelected(sym)} />)}
      </div>

      <div style={{ display: "flex", borderTop: "0.5px solid #eee" }}>
        {[["☰", "Watchlist", true], ["📊", "Analysis", false], ["📅", "Earnings", false], ["⚙️", "Settings", false]].map(([icon, label, active]) => (
          <div key={label} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", padding: "10px 0 12px", gap: 4, cursor: "pointer", color: active ? "#111" : "#aaa", fontSize: 10 }}>
            {active && <div style={{ height: 2, background: "#111", width: 24, borderRadius: 2, marginBottom: 2 }} />}
            <span style={{ fontSize: 20 }}>{icon}</span>
            <span>{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}