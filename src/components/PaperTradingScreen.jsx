import { useState, useEffect } from "react";
import { API_BASE } from "../data/tickers";
import TabBar from "./TabBar";

function formatDate(dateStr) {
  if (!dateStr) return "—";
  return new Date(dateStr + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatTime(isoStr) {
  if (!isoStr) return null;
  try {
    return new Date(isoStr).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  } catch {
    return null;
  }
}

function formatMoney(n) {
  if (n === null || n === undefined) return "—";
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatPrice(n) {
  if (n === null || n === undefined) return "—";
  return `$${n.toFixed(2)}`;
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

function ChangeLabel({ ticker, pct }) {
  if (pct === null || pct === undefined) return null;
  const isUp = pct > 0;
  return (
    <div style={{ fontSize: 10, color: isUp ? "var(--up)" : pct < 0 ? "var(--down)" : "var(--text4)", marginTop: 2 }}>
      {ticker} {isUp ? "+" : ""}{pct.toFixed(1)}% today
    </div>
  );
}

// Prefers the position's OWN day-over-day change (real, from Alpaca's
// historical option bars) -- falls back to the underlying's move only
// when that isn't available yet (e.g. a just-entered position with no
// prior session to diff against, or a quiet contract with no trades on
// its last session).
function TodayChange({ p }) {
  if (p.position_change_pct != null) {
    const pct = p.position_change_pct;
    const isUp = pct > 0;
    return (
      <div style={{ fontSize: 11, fontWeight: 600, fontVariantNumeric: "tabular-nums", color: isUp ? "var(--up)" : pct < 0 ? "var(--down)" : "var(--text4)", marginTop: 2 }}>
        {isUp ? "+" : ""}{pct.toFixed(1)}% today
      </div>
    );
  }
  return <ChangeLabel ticker={p.ticker} pct={p.stock_change_pct} />;
}

const PERFORMANCE_RANGES = [
  ["1D", "1D"],
  ["1W", "1W"],
  ["1M", "1M"],
  ["ALL", "All"],
];

function RangePicker({ value, onChange }) {
  return (
    <div style={{ display: "flex", gap: 4 }}>
      {PERFORMANCE_RANGES.map(([key, label]) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          style={{
            fontSize: 11, fontWeight: 500, padding: "4px 10px", borderRadius: 6,
            border: "0.5px solid var(--border)", cursor: "pointer",
            background: value === key ? "var(--text)" : "transparent",
            color: value === key ? "var(--bg)" : "var(--text3)",
          }}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

// Hand-rolled sparkline-style line chart -- no charting library in this
// project, and an equity curve is simple enough (one line, no axes/
// legend) that a small inline SVG is less overhead than adding one.
// viewBox uses fixed pixel units stretched to the container's width via
// CSS, same convention as other lightweight inline visuals in this app.
function PerformanceChart({ points, color }) {
  if (!points || points.length < 2) {
    return (
      <div style={{ height: 120, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, color: "var(--text3)" }}>
        Not enough data yet for this range.
      </div>
    );
  }

  const W = 400, H = 120, PAD = 4;
  const values = points.map(p => p.equity);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const stepX = (W - PAD * 2) / (points.length - 1);

  const coords = points.map((p, i) => [
    PAD + i * stepX,
    PAD + (1 - (p.equity - min) / range) * (H - PAD * 2),
  ]);
  const linePath = coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const areaPath = `${linePath} L${coords[coords.length - 1][0].toFixed(1)},${H - PAD} L${coords[0][0].toFixed(1)},${H - PAD} Z`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: "100%", height: 120, display: "block" }}>
      <path d={areaPath} fill={color} opacity={0.12} stroke="none" />
      <path d={linePath} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// Live positions refresh on their own timer -- separate from the one-time
// summary/trade-history load, so opening the screen doesn't wait on an
// Alpaca round trip, and the estimated value stays reasonably current
// while the screen is open.
const POSITIONS_LIVE_POLL_MS = 60000;

export default function PaperTradingScreen({ onTab }) {
  const [summary, setSummary] = useState(null);
  const [positions, setPositions] = useState([]);
  const [trades, setTrades] = useState([]);
  const [account, setAccount] = useState(null);
  const [perfRange, setPerfRange] = useState("1M");
  const [perfData, setPerfData] = useState(null);
  const [perfLoading, setPerfLoading] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetch(`${API_BASE}/paper-trading/summary`).then(r => r.json()),
      fetch(`${API_BASE}/paper-trading/positions-live`).then(r => r.json()),
      fetch(`${API_BASE}/paper-trading/trades`).then(r => r.json()),
      fetch(`${API_BASE}/paper-trading/account`).then(r => r.json()),
    ])
      .then(([summaryData, positionsData, tradesData, accountData]) => {
        setSummary(summaryData);
        setPositions(positionsData.positions || []);
        setTrades(tradesData.trades || []);
        setAccount(accountData);
        setLoading(false);
      })
      .catch(() => {
        setError("Unable to load paper trading data. Try again shortly.");
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      fetch(`${API_BASE}/paper-trading/positions-live`)
        .then(r => r.json())
        .then(d => setPositions(d.positions || []))
        .catch(() => {}); // keep showing the last good values on a transient failure
    }, POSITIONS_LIVE_POLL_MS);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      fetch(`${API_BASE}/paper-trading/account`)
        .then(r => r.json())
        .then(setAccount)
        .catch(() => {});
    }, POSITIONS_LIVE_POLL_MS);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    setPerfLoading(true);
    fetch(`${API_BASE}/paper-trading/performance?range=${perfRange}`)
      .then(r => r.json())
      .then(d => {
        setPerfData(d);
        setPerfLoading(false);
      })
      .catch(() => setPerfLoading(false));
  }, [perfRange]);

  const closedTrades = trades.filter(t => t.status === "closed");
  const perfPoints = perfData && perfData.points;
  const perfUp = perfPoints && perfPoints.length > 1
    ? perfPoints[perfPoints.length - 1].equity >= perfPoints[0].equity
    : true;

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
            {account && (
              <div style={{ padding: "16px 20px 4px" }}>
                <div style={{ fontSize: 11, color: "var(--text3)", marginBottom: 2 }}>Account Value</div>
                <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
                  <div style={{ fontSize: 28, fontWeight: 600, color: "var(--text)", fontVariantNumeric: "tabular-nums" }}>
                    {formatMoney(account.equity)}
                  </div>
                  {account.day_change_pct != null && (
                    <div style={{
                      fontSize: 13, fontWeight: 600, fontVariantNumeric: "tabular-nums",
                      color: account.day_change_pct > 0 ? "var(--up)" : account.day_change_pct < 0 ? "var(--down)" : "var(--text4)",
                    }}>
                      {account.day_change_pct > 0 ? "+" : ""}{account.day_change_pct.toFixed(2)}%
                    </div>
                  )}
                </div>
                {account.day_change_usd != null && (
                  <div style={{ fontSize: 11, color: "var(--text4)", marginTop: 2 }}>
                    {account.day_change_usd > 0 ? "+" : ""}{formatMoney(account.day_change_usd)} today
                  </div>
                )}
              </div>
            )}

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

            <div style={{ padding: "18px 20px 8px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>Performance</div>
              <RangePicker value={perfRange} onChange={setPerfRange} />
            </div>
            <div style={{ padding: "0 20px 4px" }}>
              {perfLoading ? (
                <div style={{ height: 120, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, color: "var(--text3)" }}>
                  Loading…
                </div>
              ) : (
                <PerformanceChart points={perfPoints} color={perfUp ? "var(--up)" : "var(--down)"} />
              )}
              {perfPoints && perfPoints.length > 1 && (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 10, color: "var(--text4)", marginTop: 4 }}>
                  <span style={{ fontVariantNumeric: "tabular-nums" }}>{formatMoney(perfPoints[0].equity)}</span>
                  <PnlBadge pct={perfPoints[perfPoints.length - 1].pnl_pct} />
                  <span style={{ fontVariantNumeric: "tabular-nums" }}>{formatMoney(perfPoints[perfPoints.length - 1].equity)}</span>
                </div>
              )}
            </div>

            <div style={{ padding: "18px 20px 6px", fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
              Open Positions
            </div>
            {positions.length === 0 ? (
              <div style={{ padding: "0 20px 8px", fontSize: 12, color: "var(--text3)" }}>No open positions right now.</div>
            ) : positions.map(p => {
              const entryTime = formatTime(p.entry_time);
              const hasLive = p.current_value_usd != null;
              return (
                <div key={p.id} style={{ display: "flex", alignItems: "flex-start", padding: "12px 20px", borderBottom: "0.5px solid var(--border)", gap: 10 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 15, fontWeight: 500, color: "var(--text)" }}>{p.ticker}</div>
                    <div style={{ fontSize: 11, color: "var(--text3)" }}>
                      Entered {formatDate(p.entry_date)}{entryTime ? ` at ${entryTime}` : ""} · earnings {formatDate(p.er_date)}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text3)", marginTop: 2, fontVariantNumeric: "tabular-nums" }}>
                      Entry {formatPrice(p.entry_cost)}{hasLive ? ` → now ${formatPrice(p.current_straddle_price)}` : ""}
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 12, color: "var(--text2)", fontVariantNumeric: "tabular-nums" }}>
                      {hasLive ? formatMoney(p.current_value_usd) : formatMoney(p.position_size_usd)}
                    </div>
                    {hasLive && p.unrealized_pnl_pct != null && (
                      <div style={{ marginTop: 2 }}><PnlBadge pct={p.unrealized_pnl_pct} /></div>
                    )}
                    <TodayChange p={p} />
                    <div style={{ fontSize: 10, color: "var(--text4)", marginTop: 2 }}>
                      predicted +{(p.predicted_log_ratio * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>
              );
            })}

            <div style={{ padding: "18px 20px 6px", fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
              Trade History
            </div>
            {closedTrades.length === 0 ? (
              <div style={{ padding: "0 20px 8px", fontSize: 12, color: "var(--text3)" }}>No closed trades yet.</div>
            ) : closedTrades.map(t => {
              const entryTime = formatTime(t.entry_time);
              return (
                <div key={t.id} style={{ display: "flex", alignItems: "flex-start", padding: "12px 20px", borderBottom: "0.5px solid var(--border)", gap: 10 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 15, fontWeight: 500, color: "var(--text)" }}>{t.ticker}</div>
                    <div style={{ fontSize: 11, color: "var(--text3)" }}>
                      {formatDate(t.entry_date)}{entryTime ? ` ${entryTime}` : ""} → {formatDate(t.exit_date)}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text3)", marginTop: 2, fontVariantNumeric: "tabular-nums" }}>
                      Entry {formatPrice(t.entry_cost)} → exit {formatPrice(t.exit_value)}
                    </div>
                  </div>
                  <PnlBadge pct={t.pnl_pct} />
                </div>
              );
            })}
          </>
        )}
      </div>

      <TabBar active="Trading" onTab={onTab} />
    </div>
  );
}
