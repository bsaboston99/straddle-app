import { useState, useEffect } from "react";
import { tickers } from "../data/tickers";
import { MiniBar, CompositeBadge } from "./MiniBar";
import TabBar from "./TabBar";
import { API_BASE } from "../data/tickers";

function StraddleChart({ sym, mockLiveA }) {
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/history/${sym}?dbe=0`)
      .then(r => r.json())
      .then(d => { setHistory(d.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [sym]);

  if (loading) return (
    <div style={{ height: 180, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text3)", fontSize: 12 }}>
      Loading chart...
    </div>
  );
  if (!history || history.length === 0) return (
    <div style={{ height: 180, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text3)", fontSize: 12 }}>
      No chart data available
    </div>
  );

  const W = 340;
  const PAD = { left: 44, right: 12 };
  const innerW = W - PAD.left - PAD.right;

  // Straddle chart
  const SH = 90, SPAD = { top: 10, bottom: 6 };
  const sInnerH = SH - SPAD.top - SPAD.bottom;
  const values_a = history.map(d => d.closestraddle_a);
  const values_b = history.map(d => d.closestraddle_b);
  const allVals = [...values_a, ...values_b];
  if (mockLiveA) allVals.push(mockLiveA);
  const sMinY = 0;
  const sMaxY = Math.ceil(Math.max(...allVals) * 100 * 1.1) / 100;
  const xScale = i => PAD.left + (i / (history.length - 1)) * innerW;
  const sYScale = v => SPAD.top + sInnerH - ((v - sMinY) / (sMaxY - sMinY)) * sInnerH;
  const pathA = history.map((d, i) => `${i === 0 ? "M" : "L"}${xScale(i).toFixed(1)},${sYScale(d.closestraddle_a).toFixed(1)}`).join(" ");
  const pathB = history.map((d, i) => `${i === 0 ? "M" : "L"}${xScale(i).toFixed(1)},${sYScale(d.closestraddle_b).toFixed(1)}`).join(" ");
  const sTickCount = 4;
  const sRawStep = sMaxY / sTickCount;
  const sMag = Math.pow(10, Math.floor(Math.log10(sRawStep)));
  const sNiceStep = Math.ceil(sRawStep / sMag) * sMag;
  const sYTicks = [0, 1, 2, 3, 4].map(i => parseFloat((i * sNiceStep).toFixed(4)));

  // Move chart
  const MH = 80, MPAD = { top: 6, bottom: 30 };
  const mInnerH = MH - MPAD.top - MPAD.bottom;
  const allPcts = history.flatMap(d => [d.open_chg_pct, d.close_chg_pct].filter(v => v !== null));
  const mMinY = Math.min(...allPcts, 0);
  const mMaxY = Math.max(...allPcts, 0);
  const mAbsMax = Math.ceil(Math.max(Math.abs(mMinY), Math.abs(mMaxY)) * 10) / 10;
  const mRange = mAbsMax * 2 || 1;
  const mYScale = v => MPAD.top + mInnerH - ((v + mAbsMax) / mRange) * mInnerH;
  const mStep = parseFloat((mAbsMax / 2).toFixed(1));
  const mYTicks = [-mAbsMax, -mStep, 0, mStep, mAbsMax];
  const xLabels = history.map((d, i) => {
    const parts = d.date.split("-");
    return { i, label: `${parts[1]}/${parts[0].slice(2)}` };
  });

  return (
    <div>
      {/* Legend */}
      <div style={{ display: "flex", gap: 12, marginBottom: 6, flexWrap: "wrap" }}>
        {[
          { w: 10, h: 2, bg: "var(--up)",   label: "ER" },
          { w: 10, h: 2, bg: "var(--blue)", label: "ER+1", dashed: true },
        ].map(({ w, h, bg, label, dashed }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <div style={{ width: w, height: h, background: bg, ...(dashed ? { backgroundImage: `repeating-linear-gradient(to right, ${bg} 0 3px, transparent 3px 5px)`, background: "none", borderTop: `2px dashed ${bg}`, height: 0 } : {}) }} />
            <span style={{ fontSize: 10, color: "var(--text3)" }}>{label}</span>
          </div>
        ))}
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div style={{ width: 8, height: 8, background: "var(--up-bg)", border: "1px solid var(--up)", borderRadius: 1 }} />
          <span style={{ fontSize: 10, color: "var(--text3)" }}>Post open→close</span>
        </div>
        {mockLiveA && (
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--earn-bg)", border: "1.5px solid var(--earn-text)" }} />
            <span style={{ fontSize: 10, color: "var(--text3)" }}>Current</span>
          </div>
        )}
      </div>

      {/* Straddle chart */}
      <div style={{ fontSize: 10, color: "var(--text3)", marginBottom: 2 }}>DBE=0 Straddle Value</div>
      <svg viewBox={`0 0 ${W} ${SH}`} style={{ width: "100%", height: SH }}>
        {sYTicks.map((v, i) => (
          <g key={i}>
            <line x1={PAD.left} y1={sYScale(v)} x2={W - PAD.right} y2={sYScale(v)} stroke="var(--chart-grid)" strokeWidth="0.5" />
            <text x={PAD.left - 4} y={sYScale(v) + 3} fontSize="8" fill="var(--chart-axis)" textAnchor="end">
              {(v * 100).toFixed(1)}%
            </text>
          </g>
        ))}
        <path d={pathB} fill="none" stroke="var(--blue)" strokeWidth="1.2" strokeDasharray="3,2" />
        <path d={pathA} fill="none" stroke="var(--up)" strokeWidth="1.5" />
        {history.map((d, i) => (
          <circle key={i} cx={xScale(i)} cy={sYScale(d.closestraddle_a)} r="2.5" fill="var(--up)" />
        ))}
        {mockLiveA && (
          <circle cx={W - PAD.right} cy={sYScale(mockLiveA)} r="4" fill="var(--earn-bg)" stroke="var(--earn-text)" strokeWidth="1.5" />
        )}
      </svg>

      {/* Move chart */}
      <div style={{ fontSize: 10, color: "var(--text3)", marginTop: 8, marginBottom: 2 }}>Post-Earnings Stock Move (%)</div>
      <svg viewBox={`0 0 ${W} ${MH}`} style={{ width: "100%", height: MH }}>
        {mYTicks.map((v, i) => (
          <g key={i}>
            <line
              x1={PAD.left} y1={mYScale(v)} x2={W - PAD.right} y2={mYScale(v)}
              stroke={v === 0 ? "var(--chart-zero)" : "var(--chart-grid)"}
              strokeWidth={v === 0 ? "1" : "0.5"}
            />
            <text x={PAD.left - 4} y={mYScale(v) + 3} fontSize="8" fill="var(--chart-axis)" textAnchor="end">
              {v > 0 ? `+${v.toFixed(1)}` : `${v.toFixed(1)}`}%
            </text>
          </g>
        ))}
        {history.map((d, i) => {
          const x = xScale(i);
          const openPct = d.open_chg_pct;
          const closePct = d.close_chg_pct;
          if (openPct === null || closePct === null) return null;
          const yOpen  = mYScale(openPct);
          const yClose = mYScale(closePct);
          const yTop   = Math.min(yOpen, yClose);
          const yBot   = Math.max(yOpen, yClose);
          const isUp   = closePct >= 0;
          return (
            <g key={i}>
              <rect
                x={x - 3} y={yTop} width={6} height={Math.max(yBot - yTop, 1)}
                fill={isUp ? "var(--up-bg)" : "var(--down-bg)"}
                stroke={isUp ? "var(--up)" : "var(--down)"} strokeWidth="0.5"
              />
              <circle cx={x} cy={yOpen}  r="2"   fill="var(--text3)" />
              <circle cx={x} cy={yClose} r="2.5" fill={isUp ? "var(--up)" : "var(--down)"} />
            </g>
          );
        })}
        {xLabels.map(({ i, label }) => (
          <text key={i} x={xScale(i)} y={MH - 4} fontSize="7" fill="var(--chart-axis)"
            textAnchor="middle" transform={`rotate(-45, ${xScale(i)}, ${MH - 4})`}>
            {label}
          </text>
        ))}
      </svg>

      <div style={{ fontSize: 10, color: "var(--text3)", textAlign: "center", marginTop: 2 }}>
        {history.length} earnings cycles · gray dot = open · colored dot = close
      </div>
    </div>
  );
}

export default function DetailScreen({ sym, onBack, onTab, straddleMap }) {
  const t = tickers[sym];
  const isUp = t.dir === "up";
  const sd = straddleMap?.[sym];

  const pct_a     = sd ? sd.pct_a         : t.pct_a;
  const pct_b     = sd ? sd.pct_b         : t.pct_b;
  const pct_ep    = sd ? sd.pct_ep        : t.pct_ep;
  const sig_a     = sd ? sd.signal_a      : t.sig_a;
  const sig_b     = sd ? sd.signal_b      : t.sig_b;
  const sig_ep    = sd ? sd.signal_ep     : t.sig_ep;
  const adj_a     = sd ? sd.adj_signal_a  : t.adj_a;
  const adj_b     = sd ? sd.adj_signal_b  : t.adj_b;
  const adj_ep    = sd ? sd.adj_signal_ep : t.adj_ep;
  const composite = sd ? sd.composite     : t.composite;

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, fontFamily: "system-ui, sans-serif", background: "var(--bg)", overflow: "hidden" }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "16px 20px 14px", borderBottom: "0.5px solid var(--border)", flexShrink: 0 }}>
        <button onClick={onBack} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 22, color: "var(--text2)", padding: 0 }}>
          &#8592;
        </button>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 18, fontWeight: 500, color: "var(--text)" }}>{sym}</div>
          <div style={{ fontSize: 12, color: "var(--text2)", marginTop: 1 }}>{t.name}</div>
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, padding: "20px", overflowY: "auto" }}>

        {/* Price hero */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 32, fontWeight: 500, color: "var(--text)" }}>{t.price}</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
            <span style={{
              background: isUp ? "var(--up-bg)" : "var(--down-bg)",
              color: isUp ? "var(--up)" : "var(--down)",
              fontSize: 13, fontWeight: 500, padding: "3px 8px", borderRadius: 5
            }}>
              {t.change}
            </span>
            <span style={{ fontSize: 12, color: "var(--text2)" }}>{t.earnInfo}</span>
          </div>
        </div>

        {/* Straddle history chart */}
        <div style={{ background: "var(--surface)", borderRadius: 8, padding: "14px 16px", marginBottom: 4 }}>
          <div style={{ fontSize: 11, fontWeight: 500, color: "var(--text2)", letterSpacing: "0.04em", textTransform: "uppercase", marginBottom: 10 }}>
            DBE=0 Straddle History
          </div>
          <StraddleChart sym={sym} mockLiveA={sd ? sd.close_a : null} />
        </div>

        {/* Straddle percentiles */}
        <div style={{ fontSize: 11, fontWeight: 500, color: "var(--text2)", letterSpacing: "0.04em", textTransform: "uppercase", margin: "20px 0 8px" }}>
          Straddle percentiles
        </div>
        <div style={{ background: "var(--surface)", borderRadius: 8, padding: "14px 16px" }}>
          <div style={{ marginBottom: 12 }}>
            <MiniBar pct={pct_a} sig={sig_a} label="ER straddle vs SPY (overall vol)" />
            <div style={{ fontSize: 11, color: "var(--text2)", marginTop: 2 }}>{adj_a}</div>
          </div>
          <div style={{ marginBottom: 12 }}>
            <MiniBar pct={pct_b} sig={sig_b} label="ER+1 straddle vs SPY (background vol)" />
            <div style={{ fontSize: 11, color: "var(--text2)", marginTop: 2 }}>{adj_b}</div>
          </div>
          <div style={{ marginBottom: 4 }}>
            <MiniBar pct={pct_ep} sig={sig_ep} label="Earnings premium (event fear)" />
            <div style={{ fontSize: 11, color: "var(--text2)", marginTop: 2 }}>{adj_ep}</div>
          </div>
          <div style={{ marginTop: 14, paddingTop: 12, borderTop: "0.5px solid var(--border)" }}>
            <span style={{ fontSize: 11, color: "var(--text2)", marginRight: 8 }}>Composite:</span>
            <CompositeBadge composite={composite} />
          </div>
        </div>

        {/* Straddle values */}
        <div style={{ fontSize: 11, fontWeight: 500, color: "var(--text2)", letterSpacing: "0.04em", textTransform: "uppercase", margin: "20px 0 10px" }}>
          Straddle values
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          {[
            { label: "ER straddle",           val: sd ? `${(sd.close_a * 100).toFixed(2)}%`   : t.front,  sub: "of stock price" },
            { label: "ER+1 straddle",          val: sd ? `${(sd.close_b * 100).toFixed(2)}%`   : t.back,   sub: "of stock price" },
            { label: "Earnings premium ratio", val: sd ? `${sd.earnings_premium.toFixed(2)}x`  : t.epr,    sub: "vs SPY baseline" },
            { label: "SPY-normalized move",    val: sd ? `${(sd.rel_a).toFixed(2)}x`           : t.spyNorm,sub: "front vs SPY front" },
          ].map(m => (
            <div key={m.label} style={{ background: "var(--surface)", borderRadius: 8, padding: 12 }}>
              <div style={{ fontSize: 11, color: "var(--text2)", marginBottom: 4 }}>{m.label}</div>
              <div style={{ fontSize: 18, fontWeight: 500, color: "var(--text)" }}>{m.val}</div>
              <div style={{ fontSize: 11, color: "var(--text3)", marginTop: 2 }}>{m.sub}</div>
            </div>
          ))}
        </div>

        {/* Key details */}
        <div style={{ fontSize: 11, fontWeight: 500, color: "var(--text2)", letterSpacing: "0.04em", textTransform: "uppercase", margin: "20px 0 10px" }}>
          Key details
        </div>
        {[
          { label: "Earnings date",       val: t.earnDate },
          { label: "52-week range",       val: t.wk52 },
          { label: "Implied volatility",  val: t.iv },
          { label: "IV rank",             val: t.ivr },
          { label: "Historical move avg", val: t.hist },
        ].map(r => (
          <div key={r.label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0", borderBottom: "0.5px solid var(--border)" }}>
            <span style={{ fontSize: 13, color: "var(--text2)" }}>{r.label}</span>
            <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text)" }}>{r.val}</span>
          </div>
        ))}

        {/* Signal card */}
        <div style={{
          background: t.signal.type === "warn" ? "var(--warn-bg)" : "var(--ok-bg)",
          borderRadius: 8, padding: "12px 14px", marginTop: 16, marginBottom: 8
        }}>
          <div style={{ fontSize: 11, fontWeight: 500, color: t.signal.type === "warn" ? "var(--warn-text)" : "var(--ok-text)", marginBottom: 2 }}>
            {t.signal.label}
          </div>
          <div style={{ fontSize: 13, color: t.signal.type === "warn" ? "var(--warn-body)" : "var(--ok-body)" }}>
            {t.signal.text}
          </div>
        </div>

      </div>

      <TabBar active="Watchlist" onTab={onTab} />
    </div>
  );
}
