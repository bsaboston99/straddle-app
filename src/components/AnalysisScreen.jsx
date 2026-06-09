import { useState, useEffect } from "react";
import { API_BASE } from "../data/tickers";
import TabBar from "./TabBar";
import AnalysisDetailScreen from "./AnalysisDetailScreen";
import { IconSearch } from "./Icons";

const DBE_OPTIONS = [0, 1, 2, 3, 4, 5];

function TickerRow({ item, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{ display: "flex", alignItems: "center", padding: "13px 16px", borderBottom: "0.5px solid var(--border)", cursor: "pointer", gap: 12 }}
    >
      {/* Ticker + sample size */}
      <div style={{ width: 60, flexShrink: 0 }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text)" }}>{item.ticker}</div>
        <div style={{ fontSize: 11, color: "var(--text4)", marginTop: 2 }}>n = {item.n}</div>
      </div>

      {/* Stats */}
      <div style={{ flex: 1, display: "flex", gap: 0, flexDirection: "column" }}>
        <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
          <span style={{ fontSize: 11, color: "var(--text3)" }}>Avg</span>
          <span style={{ fontSize: 15, fontWeight: 500, color: "var(--text)" }}>
            {(item.mean_a * 100).toFixed(2)}%
          </span>
          <span style={{ fontSize: 11, color: "var(--text3)", marginLeft: 4 }}>±</span>
          <span style={{ fontSize: 14, fontWeight: 400, color: "var(--text2)" }}>
            {(item.std_a * 100).toFixed(2)}%
          </span>
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 4, fontSize: 11, color: "var(--text4)" }}>
          <span>25th {(item.pct_25_a * 100).toFixed(2)}%</span>
          <span>·</span>
          <span>Med {(item.median_a * 100).toFixed(2)}%</span>
          <span>·</span>
          <span>75th {(item.pct_75_a * 100).toFixed(2)}%</span>
        </div>
      </div>

      {/* Chevron */}
      <span style={{ color: "var(--text4)", fontSize: 16, flexShrink: 0 }}>›</span>
    </div>
  );
}

export default function AnalysisScreen({ onTab }) {
  const [dbe, setDbe] = useState(0);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    setLoading(true);
    setData(null);
    setError(null);
    fetch(`${API_BASE}/analysis?dbe=${dbe}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => { setError("Failed to load analysis data."); setLoading(false); });
  }, [dbe]);

  if (selected) {
    return (
      <AnalysisDetailScreen
        ticker={selected}
        onBack={() => setSelected(null)}
        onTab={onTab}
      />
    );
  }

  const query = search.trim().toUpperCase();
  const filtered = data?.tickers
    ? (query ? data.tickers.filter(t => t.ticker.includes(query)) : data.tickers)
    : [];

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, fontFamily: "system-ui, sans-serif", background: "var(--bg)", overflow: "hidden" }}>

      {/* Header */}
      <div style={{ padding: "18px 20px 12px", borderBottom: "0.5px solid var(--border)", flexShrink: 0 }}>
        <h1 style={{ fontSize: 20, fontWeight: 500, margin: "0 0 12px", color: "var(--text)" }}>Analysis</h1>

        {/* DBE selector */}
        <div style={{ display: "flex", gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
          {DBE_OPTIONS.map(d => (
            <button
              key={d}
              onClick={() => { setDbe(d); setSearch(""); }}
              style={{
                padding: "5px 14px", borderRadius: 20, fontSize: 12, fontWeight: 500,
                border: dbe === d ? "1.5px solid var(--text)" : "0.5px solid var(--border)",
                background: dbe === d ? "var(--text)" : "var(--surface)",
                color: dbe === d ? "var(--bg)" : "var(--text2)",
                cursor: "pointer", fontFamily: "system-ui, sans-serif"
              }}
            >
              DBE {d}
            </button>
          ))}
        </div>

        {/* Search */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, background: "var(--surface)", borderRadius: 8, padding: "8px 12px" }}>
          <IconSearch size={15} color="var(--text4)" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search tickers..."
            autoCapitalize="characters"
            autoCorrect="off"
            spellCheck={false}
            style={{ flex: 1, fontSize: 14, color: "var(--text)", background: "none", border: "none", outline: "none" }}
          />
          {search && (
            <span onClick={() => setSearch("")} style={{ color: "var(--text4)", fontSize: 16, cursor: "pointer", padding: "0 2px", lineHeight: 1 }}>×</span>
          )}
        </div>
      </div>

      {/* Count strip */}
      {!loading && data && (
        <div style={{ padding: "6px 16px", flexShrink: 0, borderBottom: "0.5px solid var(--border)", background: "var(--surface)" }}>
          <span style={{ fontSize: 10, color: "var(--text4)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            {filtered.length} ticker{filtered.length !== 1 ? "s" : ""} · DBE={dbe} · closestraddle_a historical stats
          </span>
        </div>
      )}

      {/* List */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {loading && (
          <div style={{ padding: "60px 20px", textAlign: "center", color: "var(--text3)", fontSize: 13 }}>
            Scanning parquet data...
          </div>
        )}
        {error && (
          <div style={{ padding: "60px 20px", textAlign: "center", color: "var(--down)", fontSize: 13 }}>{error}</div>
        )}
        {!loading && !error && filtered.length === 0 && data && (
          <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--text3)", fontSize: 13 }}>
            {query ? `No results for "${search}"` : `No tickers with ≥3 observations at DBE=${dbe}`}
          </div>
        )}
        {filtered.map(item => (
          <TickerRow key={item.ticker} item={item} onClick={() => setSelected(item.ticker)} />
        ))}
      </div>

      <TabBar active="Analysis" onTab={onTab} />
    </div>
  );
}
