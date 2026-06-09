import { useState, useEffect } from "react";
import { API_BASE } from "../data/tickers";
import TabBar from "./TabBar";

// ── Straddle + move history chart (pure historical, no live data) ──────────
function HistoryChart({ history }) {
  if (!history || history.length === 0) return (
    <div style={{ height: 180, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text3)", fontSize: 12 }}>
      No chart data
    </div>
  );

  const W = 340;
  const PAD = { left: 44, right: 12 };
  const innerW = W - PAD.left - PAD.right;

  // ── Straddle line chart ──────────────────────────────────────────────────
  const SH = 90, SPAD = { top: 10, bottom: 6 };
  const sInnerH = SH - SPAD.top - SPAD.bottom;
  const vals_a = history.map(d => d.closestraddle_a);
  const sMaxY = Math.ceil(Math.max(...vals_a) * 100 * 1.1) / 100;
  const xScale = i => PAD.left + (i / Math.max(history.length - 1, 1)) * innerW;
  const sYScale = v => SPAD.top + sInnerH - (v / sMaxY) * sInnerH;

  const pathA = history
    .map((d, i) => `${i === 0 ? "M" : "L"}${xScale(i).toFixed(1)},${sYScale(d.closestraddle_a).toFixed(1)}`)
    .join(" ");

  const sTickCount = 4;
  const sRawStep = sMaxY / sTickCount;
  const sMag = Math.pow(10, Math.floor(Math.log10(sRawStep)));
  const sNiceStep = Math.ceil(sRawStep / sMag) * sMag;
  const sYTicks = [0, 1, 2, 3, 4].map(i => parseFloat((i * sNiceStep).toFixed(4)));

  // ── Post-earnings move chart ─────────────────────────────────────────────
  const MH = 80, MPAD = { top: 6, bottom: 30 };
  const mInnerH = MH - MPAD.top - MPAD.bottom;
  const allPcts = history.flatMap(d => [d.open_chg_pct, d.close_chg_pct].filter(v => v != null));
  const mAbsMax = allPcts.length ? Math.ceil(Math.max(...allPcts.map(Math.abs)) * 10) / 10 : 5;
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
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div style={{ width: 10, height: 2, background: "var(--up)" }} />
          <span style={{ fontSize: 10, color: "var(--text3)" }}>DBE=0 Straddle A</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div style={{ width: 8, height: 8, background: "var(--up-bg)", border: "1px solid var(--up)", borderRadius: 1 }} />
          <span style={{ fontSize: 10, color: "var(--text3)" }}>Post-earnings move</span>
        </div>
      </div>

      {/* Straddle line */}
      <div style={{ fontSize: 10, color: "var(--text3)", marginBottom: 2 }}>Straddle A at DBE=0</div>
      <svg viewBox={`0 0 ${W} ${SH}`} style={{ width: "100%", height: SH }}>
        {sYTicks.map((v, i) => (
          <g key={i}>
            <line x1={PAD.left} y1={sYScale(v)} x2={W - PAD.right} y2={sYScale(v)} stroke="var(--chart-grid)" strokeWidth="0.5" />
            <text x={PAD.left - 4} y={sYScale(v) + 3} fontSize="8" fill="var(--chart-axis)" textAnchor="end">
              {(v * 100).toFixed(1)}%
            </text>
          </g>
        ))}
        <path d={pathA} fill="none" stroke="var(--up)" strokeWidth="1.5" />
        {history.map((d, i) => (
          <circle key={i} cx={xScale(i)} cy={sYScale(d.closestraddle_a)} r="2.5" fill="var(--up)" />
        ))}
      </svg>

      {/* Move bars */}
      <div style={{ fontSize: 10, color: "var(--text3)", marginTop: 8, marginBottom: 2 }}>Post-Earnings Move (%)</div>
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
          if (d.open_chg_pct == null || d.close_chg_pct == null) return null;
          const x = xScale(i);
          const yOpen  = mYScale(d.open_chg_pct);
          const yClose = mYScale(d.close_chg_pct);
          const isUp   = d.close_chg_pct >= 0;
          return (
            <g key={i}>
              <rect
                x={x - 3} y={Math.min(yOpen, yClose)}
                width={6} height={Math.max(Math.abs(yClose - yOpen), 1)}
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
        {history.length} earnings cycles · gray = open · colored = close
      </div>
    </div>
  );
}

// ── Colour helpers ─────────────────────────────────────────────────────────
function chgColor(val) {
  if (val == null) return "var(--text4)";
  return val >= 0 ? "var(--up)" : "var(--down)";
}
function chgBg(val) {
  if (val == null) return "transparent";
  return val >= 0 ? "var(--up-bg)" : "var(--down-bg)";
}
function fmtChg(val) {
  if (val == null) return "–";
  return (val >= 0 ? "+" : "") + val.toFixed(2) + "%";
}
function fmtDate(dateStr) {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "2-digit" });
}

// ── Per-earnings event card ─────────────────────────────────────────────────
function EventCard({ row, index }) {
  const isUp = row.close_chg_pct != null && row.close_chg_pct >= 0;

  return (
    <div style={{
      margin: "0 16px 10px",
      background: "var(--surface)",
      borderRadius: 10,
      overflow: "hidden",
      border: "0.5px solid var(--border)"
    }}>
      {/* Header row: date + er_date + time badge */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "10px 14px 8px",
        borderBottom: "0.5px solid var(--border)"
      }}>
        <div>
          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
            DBE=0: {fmtDate(row.date)}
          </span>
          {row.er_date && row.er_date !== "NaT" && (
            <span style={{ fontSize: 11, color: "var(--text3)", marginLeft: 8 }}>
              ER: {fmtDate(row.er_date)}
            </span>
          )}
        </div>
        <span style={{ fontSize: 10, color: "var(--text4)" }}>#{index + 1}</span>
      </div>

      {/* Stats grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 0 }}>

        {/* Straddle A */}
        <div style={{ padding: "10px 14px", borderRight: "0.5px solid var(--border)" }}>
          <div style={{ fontSize: 10, color: "var(--text3)", marginBottom: 3, textTransform: "uppercase", letterSpacing: "0.04em" }}>Straddle A</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: "var(--text)" }}>
            {row.closestraddle_a != null ? (row.closestraddle_a * 100).toFixed(2) + "%" : "–"}
          </div>
          <div style={{ fontSize: 10, color: "var(--text4)", marginTop: 2 }}>of price</div>
        </div>

        {/* Stock close */}
        <div style={{ padding: "10px 14px", borderRight: "0.5px solid var(--border)" }}>
          <div style={{ fontSize: 10, color: "var(--text3)", marginBottom: 3, textTransform: "uppercase", letterSpacing: "0.04em" }}>Close (pre-ER)</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: "var(--text)" }}>
            {row.stock_close != null ? "$" + row.stock_close.toFixed(2) : "–"}
          </div>
          <div style={{ fontSize: 10, color: "var(--text4)", marginTop: 2 }}>stock price</div>
        </div>

        {/* Report time placeholder */}
        <div style={{ padding: "10px 14px" }}>
          <div style={{ fontSize: 10, color: "var(--text3)", marginBottom: 3, textTransform: "uppercase", letterSpacing: "0.04em" }}>Reported</div>
          <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text2)" }}>–</div>
          <div style={{ fontSize: 10, color: "var(--text4)", marginTop: 2 }}>AMC/BMO</div>
        </div>

      </div>

      {/* Post-ER moves */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", borderTop: "0.5px solid var(--border)" }}>

        <div style={{ padding: "10px 14px", borderRight: "0.5px solid var(--border)" }}>
          <div style={{ fontSize: 10, color: "var(--text3)", marginBottom: 5, textTransform: "uppercase", letterSpacing: "0.04em" }}>Open Δ</div>
          <span style={{
            fontSize: 15, fontWeight: 600,
            color: chgColor(row.open_chg_pct),
            background: chgBg(row.open_chg_pct),
            padding: row.open_chg_pct != null ? "2px 7px" : 0,
            borderRadius: 5
          }}>
            {fmtChg(row.open_chg_pct)}
          </span>
          <div style={{ fontSize: 10, color: "var(--text4)", marginTop: 4 }}>next open vs prev close</div>
        </div>

        <div style={{ padding: "10px 14px" }}>
          <div style={{ fontSize: 10, color: "var(--text3)", marginBottom: 5, textTransform: "uppercase", letterSpacing: "0.04em" }}>Close Δ</div>
          <span style={{
            fontSize: 15, fontWeight: 600,
            color: chgColor(row.close_chg_pct),
            background: chgBg(row.close_chg_pct),
            padding: row.close_chg_pct != null ? "2px 7px" : 0,
            borderRadius: 5
          }}>
            {fmtChg(row.close_chg_pct)}
          </span>
          <div style={{ fontSize: 10, color: "var(--text4)", marginTop: 4 }}>next close vs prev close</div>
        </div>

      </div>
    </div>
  );
}

// ── Main screen ────────────────────────────────────────────────────────────
export default function AnalysisDetailScreen({ ticker, onBack, onTab }) {
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/history/${ticker}?dbe=0`)
      .then(r => r.json())
      .then(d => { setHistory(d.data); setLoading(false); })
      .catch(() => { setError("Failed to load history."); setLoading(false); });
  }, [ticker]);

  // Sort oldest → newest for the chart; newest → oldest for the table
  const chronological = history ? [...history].sort((a, b) => a.date.localeCompare(b.date)) : [];
  const tableRows     = history ? [...history].sort((a, b) => b.date.localeCompare(a.date)) : [];

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, fontFamily: "system-ui, sans-serif", background: "var(--bg)", overflow: "hidden" }}>

      {/* Header */}
      <div className="safe-top" style={{ display: "flex", alignItems: "center", gap: 12, padding: "16px 20px 14px", borderBottom: "0.5px solid var(--border)", flexShrink: 0 }}>
        <button onClick={onBack} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 22, color: "var(--text2)", padding: 0 }}>
          &#8592;
        </button>
        <div>
          <div style={{ fontSize: 18, fontWeight: 500, color: "var(--text)" }}>{ticker}</div>
          <div style={{ fontSize: 12, color: "var(--text2)", marginTop: 1 }}>DBE=0 · Historical earnings breakdown</div>
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflowY: "auto" }}>

        {loading && (
          <div style={{ padding: "60px 20px", textAlign: "center", color: "var(--text3)", fontSize: 13 }}>
            Loading history...
          </div>
        )}

        {error && (
          <div style={{ padding: "60px 20px", textAlign: "center", color: "var(--down)", fontSize: 13 }}>
            {error}
          </div>
        )}

        {!loading && !error && chronological.length > 0 && (
          <>
            {/* Chart */}
            <div style={{ background: "var(--surface)", margin: "16px 16px 0", borderRadius: 10, padding: "14px 16px", border: "0.5px solid var(--border)" }}>
              <div style={{ fontSize: 11, fontWeight: 500, color: "var(--text2)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 10 }}>
                Straddle History
              </div>
              <HistoryChart history={chronological} />
            </div>

            {/* Table header */}
            <div style={{ padding: "16px 16px 8px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text2)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                Earnings Events
              </span>
              <span style={{ fontSize: 11, color: "var(--text4)" }}>{tableRows.length} cycles</span>
            </div>

            {/* Event cards */}
            {tableRows.map((row, i) => (
              <EventCard key={row.date} row={row} index={tableRows.length - 1 - i} />
            ))}

            <div style={{ height: 16 }} />
          </>
        )}

        {!loading && !error && chronological.length === 0 && (
          <div style={{ padding: "60px 20px", textAlign: "center", color: "var(--text3)", fontSize: 13 }}>
            No DBE=0 history for {ticker}
          </div>
        )}
      </div>

      <TabBar active="Analysis" onTab={onTab} />
    </div>
  );
}
