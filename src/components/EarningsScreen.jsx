import { useState, useEffect } from "react";
import { API_BASE, WATCHLIST } from "../data/tickers";
import TabBar from "./TabBar";

const FILTERS = [
  { key: "all", label: "All" },
  { key: "sp500", label: "S&P 500" },
  { key: "nasdaq100", label: "Nasdaq 100" },
  { key: "highvol", label: "High Vol" },
];

function formatDate(dateStr) {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

function daysUntil(dateStr) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const d = new Date(dateStr + "T00:00:00");
  const diff = Math.round((d - today) / (1000 * 60 * 60 * 24));
  if (diff === 0) return "Today";
  if (diff === 1) return "Tomorrow";
  return `In ${diff} days`;
}

function TimeBadge({ time }) {
  if (!time || time === "TBD") return <span style={{ fontSize: 11, color: "#aaa" }}>Time TBD</span>;
  const isBMO = time === "BMO" || time.toLowerCase().includes("before");
  const isAMC = time === "AMC" || time.toLowerCase().includes("after");
  if (isBMO) return (
    <span style={{ background: "#E6F1FB", color: "#185FA5", fontSize: 10, fontWeight: 500, padding: "2px 6px", borderRadius: 4 }}>
      Before open
    </span>
  );
  if (isAMC) return (
    <span style={{ background: "#F3EBF9", color: "#6B21A8", fontSize: 10, fontWeight: 500, padding: "2px 6px", borderRadius: 4 }}>
      After close
    </span>
  );
  return <span style={{ fontSize: 11, color: "#aaa" }}>{time}</span>;
}

export default function EarningsScreen({ onTab }) {
  const [universe, setUniverse] = useState("all");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setData(null);
    fetch(`${API_BASE}/earnings?universe=${universe}&weeks=4`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => { setError("Unable to load earnings data. Try again shortly."); setLoading(false); });
  }, [universe]);

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, fontFamily: "system-ui, sans-serif" }}>

      {/* Header */}
      <div style={{ padding: "18px 20px 12px", borderBottom: "0.5px solid #eee" }}>
        <h1 style={{ fontSize: 20, fontWeight: 500, margin: "0 0 14px" }}>Earnings Calendar</h1>
        <div style={{ display: "flex", gap: 8 }}>
          {FILTERS.map(f => (
            <button
              key={f.key}
              onClick={() => setUniverse(f.key)}
              style={{
                flex: 1, padding: "6px 0", fontSize: 11, fontWeight: 500,
                borderRadius: 6,
                border: universe === f.key ? "1.5px solid #111" : "0.5px solid #ddd",
                background: universe === f.key ? "#111" : "#fff",
                color: universe === f.key ? "#fff" : "#666",
                cursor: "pointer"
              }}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflowY: "auto", paddingBottom: 16 }}>

        {loading && (
          <div style={{ padding: "60px 20px", textAlign: "center" }}>
            <div style={{ fontSize: 13, color: "#aaa", marginBottom: 8 }}>Loading earnings data...</div>
            <div style={{ fontSize: 11, color: "#ccc" }}>Fetching from Nasdaq — may take a moment</div>
          </div>
        )}

        {error && (
          <div style={{ padding: "60px 20px", textAlign: "center" }}>
            <div style={{ fontSize: 13, color: "#A32D2D" }}>{error}</div>
          </div>
        )}

        {data && !loading && Object.keys(data.grouped).length === 0 && (
          <div style={{ padding: "60px 20px", textAlign: "center" }}>
            <div style={{ fontSize: 13, color: "#aaa" }}>No confirmed earnings in the next 4 weeks.</div>
          </div>
        )}

        {data && !loading && Object.entries(data.grouped).map(([date, items]) => (
          <div key={date}>
            {/* Date header */}
            <div style={{ padding: "12px 20px 6px", display: "flex", alignItems: "baseline", gap: 8, background: "#fafaf8", borderBottom: "0.5px solid #eee" }}>
              <span style={{ fontSize: 13, fontWeight: 600 }}>{formatDate(date)}</span>
              <span style={{ fontSize: 11, color: "#aaa" }}>{daysUntil(date)}</span>
              <span style={{ fontSize: 11, color: "#bbb", marginLeft: "auto" }}>{items.length} {items.length === 1 ? "company" : "companies"}</span>
            </div>

            {/* Ticker rows */}
            {items.map(item => {
              const isWatchlist = WATCHLIST.includes(item.ticker);
              return (
                <div
                  key={item.ticker}
                  style={{
                    display: "flex", alignItems: "center",
                    padding: "12px 20px", borderBottom: "0.5px solid #eee", gap: 10
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
                      <span style={{ fontSize: 15, fontWeight: 500 }}>{item.ticker}</span>
                      {isWatchlist && (
                        <span style={{ background: "#EAF3DE", color: "#3B6D11", fontSize: 10, fontWeight: 500, padding: "1px 5px", borderRadius: 4 }}>
                          ★ Watchlist
                        </span>
                      )}
                    </div>
                    {item.name && (
                      <div style={{ fontSize: 11, color: "#aaa" }}>{item.name}</div>
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