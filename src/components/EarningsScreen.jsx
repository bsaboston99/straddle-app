import { useState, useEffect } from "react";
import { API_BASE } from "../data/tickers";
const WATCHLIST = [];
import TabBar from "./TabBar";

const FILTERS = [
  { key: "all",       label: "All" },
  { key: "sp500",     label: "S&P 500" },
  { key: "nasdaq100", label: "Nasdaq 100" },
  { key: "highvol",   label: "High Vol" },
];

const US_HOLIDAYS = new Set([
  "2026-01-01","2026-01-19","2026-02-16","2026-04-03","2026-05-25",
  "2026-07-03","2026-09-07","2026-11-26","2026-12-25",
  "2027-01-01","2027-01-18","2027-02-15","2027-04-02","2027-05-31",
  "2027-07-05","2027-09-06","2027-11-25","2027-12-24",
]);

function isNonTradingDay(date) {
  const day = date.getDay();
  if (day === 0 || day === 6) return true;
  return US_HOLIDAYS.has(date.toISOString().split("T")[0]);
}

// lastDayToAct is the last trading day you could still act before the
// print itself: for BMO (before market open) that's the trading day
// *before* the earnings date, since the print has already happened by the
// time that date's market opens; for AMC (after close) it's the earnings
// date itself, since the print doesn't land until after that day's close.
// The displayed day-count is then "days remaining until that last
// actionable day" (count - 1), applied the same way for both BMO and AMC
// -- lastDayToAct already encodes the BMO/AMC difference above, so this
// keeps "0 Days Before Earnings" meaningful (and reachable) for both.
// (Previously this -1 step only applied to BMO, so an AMC ticker's count
// went straight from 1 to "Reported" and never showed "0 Days Before
// Earnings" -- fixed here to mirror the backend's compute_dbe, which had
// the same bug. Mirrors paper_trading.py's compute_dbe -- keep both in
// sync if this changes again.)
function tradingDaysUntil(dateStr, time) {
  if (!dateStr) return null;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const earnDate = new Date(dateStr + "T00:00:00");
  const lastDayToAct = new Date(earnDate);
  if (time === "BMO") {
    lastDayToAct.setDate(lastDayToAct.getDate() - 1);
    while (isNonTradingDay(lastDayToAct)) lastDayToAct.setDate(lastDayToAct.getDate() - 1);
  }
  const startDay = new Date(today);
  while (isNonTradingDay(startDay)) startDay.setDate(startDay.getDate() + 1);
  let count = 0;
  const cursor = new Date(startDay);
  while (cursor <= lastDayToAct) {
    if (!isNonTradingDay(cursor)) count++;
    cursor.setDate(cursor.getDate() + 1);
  }
  if (count <= 0) return "Reported";
  const d = count - 1;
  if (d === 0) return "0 Days Before Earnings";
  return `${d} Day${d !== 1 ? "s" : ""} Before Earnings`;
}

function formatDate(dateStr) {
  return new Date(dateStr + "T00:00:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

function TimeBadge({ time }) {
  if (!time || time === "TBD") return <span style={{ fontSize: 11, color: "var(--text3)" }}>Time TBD</span>;
  const isBMO = time === "BMO" || time.toLowerCase().includes("before");
  const isAMC = time === "AMC" || time.toLowerCase().includes("after");
  if (isBMO) return (
    <span style={{ background: "var(--blue-bg)", color: "var(--blue)", fontSize: 10, fontWeight: 500, padding: "2px 6px", borderRadius: 4 }}>
      Before open
    </span>
  );
  if (isAMC) return (
    <span style={{ background: "var(--purple-bg)", color: "var(--purple)", fontSize: 10, fontWeight: 500, padding: "2px 6px", borderRadius: 4 }}>
      After close
    </span>
  );
  return <span style={{ fontSize: 11, color: "var(--text3)" }}>{time}</span>;
}

export default function EarningsScreen({ onTab }) {
  const [universe, setUniverse] = useState("all");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true); setError(null); setData(null);
    fetch(`${API_BASE}/earnings?universe=${universe}&weeks=4`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => { setError("Unable to load earnings data. Try again shortly."); setLoading(false); });
  }, [universe]);

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, fontFamily: "system-ui, sans-serif", background: "var(--bg)", overflow: "hidden" }}>

      {/* paddingTop is spelled out with calc() instead of the "padding" shorthand
          -- an inline shorthand always wins over the .safe-top class's own
          padding-top rule (inline style beats stylesheet rules regardless of
          the class's specificity), which was silently discarding
          env(safe-area-inset-top) on every screen and made the header sit
          flush against the notch/status bar on a notched-phone PWA. */}
      <div className="safe-top" style={{ paddingTop: "calc(18px + env(safe-area-inset-top, 0px))", paddingRight: 20, paddingBottom: 12, paddingLeft: 20, borderBottom: "0.5px solid var(--border)", flexShrink: 0 }}>
        <h1 style={{ fontSize: 20, fontWeight: 500, margin: "0 0 14px", color: "var(--text)" }}>Earnings Calendar</h1>
        <div style={{ display: "flex", gap: 8 }}>
          {FILTERS.map(f => (
            <button
              key={f.key}
              onClick={() => setUniverse(f.key)}
              style={{
                flex: 1, padding: "6px 0", fontSize: 11, fontWeight: 500, borderRadius: 6,
                border: universe === f.key ? "1.5px solid var(--text)" : "0.5px solid var(--border)",
                background: universe === f.key ? "var(--text)" : "var(--surface)",
                color: universe === f.key ? "var(--bg)" : "var(--text2)",
                cursor: "pointer", fontFamily: "system-ui, sans-serif"
              }}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto", paddingBottom: 16 }}>
        {loading && (
          <div style={{ padding: "60px 20px", textAlign: "center" }}>
            <div style={{ fontSize: 13, color: "var(--text2)", marginBottom: 8 }}>Loading earnings data...</div>
            <div style={{ fontSize: 11, color: "var(--text3)" }}>Fetching from Nasdaq — may take a moment</div>
          </div>
        )}
        {error && (
          <div style={{ padding: "60px 20px", textAlign: "center" }}>
            <div style={{ fontSize: 13, color: "var(--down)" }}>{error}</div>
          </div>
        )}
        {data && !loading && Object.keys(data.grouped).length === 0 && (
          <div style={{ padding: "60px 20px", textAlign: "center" }}>
            <div style={{ fontSize: 13, color: "var(--text2)" }}>No confirmed earnings in the next 4 weeks.</div>
          </div>
        )}
        {data && !loading && Object.entries(data.grouped).map(([date, items]) => (
          <div key={date}>
            <div style={{ padding: "12px 20px 6px", display: "flex", alignItems: "baseline", gap: 8, background: "var(--surface)", borderBottom: "0.5px solid var(--border)" }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>{formatDate(date)}</span>
              <span style={{ fontSize: 11, color: "var(--text3)" }}>{tradingDaysUntil(date, items[0]?.time)}</span>
              <span style={{ fontSize: 11, color: "var(--text4)", marginLeft: "auto" }}>{items.length} {items.length === 1 ? "company" : "companies"}</span>
            </div>
            {items.map(item => {
              const isWatchlist = WATCHLIST.includes(item.ticker);
              return (
                <div key={item.ticker} style={{ display: "flex", alignItems: "center", padding: "12px 20px", borderBottom: "0.5px solid var(--border)", gap: 10 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
                      <span style={{ fontSize: 15, fontWeight: 500, color: "var(--text)" }}>{item.ticker}</span>
                      {isWatchlist && (
                        <span style={{ background: "var(--up-bg)", color: "var(--up)", fontSize: 10, fontWeight: 500, padding: "1px 5px", borderRadius: 4 }}>
                          ★ Watchlist
                        </span>
                      )}
                    </div>
                    {item.name && (
                      <div style={{ fontSize: 11, color: "var(--text3)" }}>
                        {item.name} · {tradingDaysUntil(item.date, item.time)}
                      </div>
                    )}
                  </div>
                  <TimeBadge time={item.time} />
                </div>
              );
            })}
          </div>
        ))}
      </div>

      <TabBar active="Earnings" onTab={onTab} />
    </div>
  );
}
