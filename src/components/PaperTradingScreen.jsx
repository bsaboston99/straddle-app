import { useState, useEffect } from "react";
import { API_BASE } from "../data/tickers";
import TabBar from "./TabBar";

function formatDate(dateStr) {
  if (!dateStr) return "—";
  return new Date(dateStr + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function StatTile({ label, value, color }) {
  return (
    <div style={{ flex: 1, padding: "12px 10px", background: "var(--surface)", borderRadius: 10, border: "0.5px solid var(--border)" }}>
      <div style={{ fontSize: 10, color: "var(--text3)", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 17, fontWeight: 600, color: color || "var(--text)", fontVariantNumeric: "tabular-nums" }}>{value}</div>
    </div>
  );
}

function PnlBadge({ pct }) {
  if (pct === null || pct === undefined) return <span style={{ fontSize: 11, color: "var(--text3)" }}>—</span>;
  const isUp = pct > 0;
  return (
    <span style={{
      fontSize: 12, fontWeight: 600, fontVariantNumeric: "tabular-nums",
      color: isUp ? "var(--up)" : "var(--down)",
    }}>
      {isUp ? "+" : ""}{pct.toFixed(1)}%
    </span>
  );
}

export default function PaperTradingScreen({ onTab }) {
  const [summary, setSummary] = useState(null);
  const [positions, setPositions] = useState([]);
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetch(`${API_BASE}/paper-trading/summary`).then(r => r.json()),
      fetch(`${API_BASE}/paper-trading/positions`).then(r => r.json()),
      fetch(`${API_BASE}/paper-trading/trades`).then(r => r.json()),
    ])
      .then(([summaryData, positionsData, tradesData]) => {
        setSummary(summaryData);
        setPositions(positionsData.positions || []);
        setTrades(tradesData.trades || []);
        setLoading(false);
      })
      .catch(() => {
        setError("Unable to load paper trading data. Try again shortly.");
        setLoading(false);
      });
  }, []);

  const closedTrades = trades.filter(t => t.status === "closed");

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, fontFamily: "system-ui, sans-serif", background: "var(--bg)", overflow: "hidden" }}>

      <div className="safe-top" style={{ padding: "18px 20px 14px", borderBottom: "0.5px solid var(--border)", flexShrink: 0 }}>
        <h1 style={{ fontSize: 20, fontWeight: 500, margin: "0 0 4px", color: "var(--text)" }}>Paper Trading</h1>
        <div style={{ fontSize: 12, color: "var(--text3)" }}>
          Earnings-straddle model, Alpaca paper account — not real money
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto", paddingBottom: 16 }}>
        {loading && (
          <div style={{ padding: "60px 20px", textAlign: "center" }}>
            <div style={{ fontSize: 13, color: "var(--text2)" }}>Loading paper trading results...</div>
          </div>
        )}
        {error && (
          <div style={{ padding: "60px 20px", textAlign: "center" }}>
            <div style={{ fontSize: 13, color: "var(--down)" }}>{error}</div>
          </div>
        )}

        {summary && !loading && !error && (
          <>
            <div style={{ display: "flex", gap: 8, padding: "16px 20px 4px" }}>
              <StatTile label="Win rate" value={summary.win_rate_pct != null ? `${summary.win_rate_pct}%` : "—"} />
              <StatTile
                label="Avg P&L"
                value={summary.avg_pnl_pct != null ? `${summary.avg_pnl_pct > 0 ? "+" : ""}${summary.avg_pnl_pct}%` : "—"}
                color={summary.avg_pnl_pct != null ? (summary.avg_pnl_pct > 0 ? "var(--up)" : "var(--down)") : undefined}
              />
              <StatTile
                label="Total P&L"
                value={summary.total_pnl_usd != null ? `$${summary.total_pnl_usd.toLocaleString()}` : "—"}
                color={summary.total_pnl_usd > 0 ? "var(--up)" : summary.total_pnl_usd < 0 ? "var(--down)" : undefined}
              />
            </div>
            <div style={{ padding: "8px 20px 4px", fontSize: 11, color: "var(--text4)" }}>
              {summary.closed_trades} closed trade{summary.closed_trades === 1 ? "" : "s"} · {summary.open_positions} open position{summary.open_positions === 1 ? "" : "s"}
            </div>

            <div style={{ padding: "18px 20px 6px", fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
              Open Positions
            </div>
            {positions.length === 0 ? (
              <div style={{ padding: "0 20px 8px", fontSize: 12, color: "var(--text3)" }}>No open positions right now.</div>
            ) : positions.map(p => (
              <div key={p.id} style={{ display: "flex", alignItems: "center", padding: "12px 20px", borderBottom: "0.5px solid var(--border)", gap: 10 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 15, fontWeight: 500, color: "var(--text)" }}>{p.ticker}</div>
                  <div style={{ fontSize: 11, color: "var(--text3)" }}>
                    Entered {formatDate(p.entry_date)} · earnings {formatDate(p.er_date)}
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: 12, color: "var(--text2)", fontVariantNumeric: "tabular-nums" }}>
                    ${p.position_size_usd?.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--text4)" }}>
                    predicted +{(p.predicted_log_ratio * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
            ))}

            <div style={{ padding: "18px 20px 6px", fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
              Trade History
            </div>
            {closedTrades.length === 0 ? (
              <div style={{ padding: "0 20px 8px", fontSize: 12, color: "var(--text3)" }}>No closed trades yet.</div>
            ) : closedTrades.map(t => (
              <div key={t.id} style={{ display: "flex", alignItems: "center", padding: "12px 20px", borderBottom: "0.5px solid var(--border)", gap: 10 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 15, fontWeight: 500, color: "var(--text)" }}>{t.ticker}</div>
                  <div style={{ fontSize: 11, color: "var(--text3)" }}>
                    {formatDate(t.entry_date)} → {formatDate(t.exit_date)}
                  </div>
                </div>
                <PnlBadge pct={t.pnl_pct} />
              </div>
            ))}
          </>
        )}
      </div>

      <TabBar active="Trading" onTab={onTab} />
    </div>
  );
}
