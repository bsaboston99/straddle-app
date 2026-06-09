import { useState, useEffect } from "react";
import WatchlistScreen from "./components/WatchlistScreen";
import DetailScreen from "./components/DetailScreen";
import AnalysisDetailScreen from "./components/AnalysisDetailScreen";
import EarningsScreen from "./components/EarningsScreen";
import AnalysisScreen from "./components/AnalysisScreen";
import SettingsScreen from "./components/SettingsScreen";
import { API_BASE, tickers } from "./data/tickers";

const WATCHLIST = ["NVDA", "ORCL", "ADBE", "TSLA", "AMZN", "META", "SPY"];

export default function App() {
  const [selected, setSelected] = useState(null);
  const [activeTab, setActiveTab] = useState("Watchlist");
  const [earningsMap, setEarningsMap] = useState({});
  const [straddleMap, setStraddleMap] = useState({});
  const [isDark, setIsDark] = useState(() => {
    try { return localStorage.getItem("theme") !== "light"; }
    catch { return true; }
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
    try { localStorage.setItem("theme", isDark ? "dark" : "light"); } catch {}
  }, [isDark]);

  useEffect(() => {
    fetch(`${API_BASE}/earnings?universe=all&weeks=8`)
      .then(r => r.json())
      .then(d => {
        const map = {};
        Object.values(d.grouped).forEach(items => {
          items.forEach(item => { map[item.ticker] = { date: item.date, time: item.time }; });
        });
        setEarningsMap(map);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const WATCHLIST = ["NVDA", "ORCL", "ADBE", "TSLA", "AMZN", "META", "SPY"];
    WATCHLIST.forEach(ticker => {
      fetch(`${API_BASE}/straddle/${ticker}?dbe=0`)
        .then(r => r.json())
        .then(d => { if (d.pct_a !== undefined) setStraddleMap(prev => ({ ...prev, [ticker]: d })); })
        .catch(() => {});
    });
  }, []);

  function handleTab(tab) {
    setSelected(null);
    setActiveTab(tab);
  }

  // Route to the right detail screen depending on whether the ticker has
  // full mock data (DetailScreen) or only parquet history (AnalysisDetailScreen).
  const selectedDetail = selected
    ? tickers[selected]
      ? <DetailScreen sym={selected} onBack={() => setSelected(null)} onTab={handleTab} earningsMap={earningsMap} straddleMap={straddleMap} />
      : <AnalysisDetailScreen ticker={selected} onBack={() => setSelected(null)} onTab={handleTab} />
    : null;

  return (
    <div style={{
      maxWidth: 430, margin: "0 auto", height: "100dvh", overflow: "hidden",
      display: "flex", flexDirection: "column",
      borderLeft: "0.5px solid var(--border)", borderRight: "0.5px solid var(--border)",
      background: "var(--bg)"
    }}>
      {selectedDetail ?? (
        activeTab === "Watchlist" ? (
          <WatchlistScreen onSelectTicker={setSelected} onTab={handleTab} earningsMap={earningsMap} straddleMap={straddleMap} />
        ) : activeTab === "Earnings" ? (
          <EarningsScreen onTab={handleTab} />
        ) : activeTab === "Analysis" ? (
          <AnalysisScreen onTab={handleTab} />
        ) : activeTab === "Settings" ? (
          <SettingsScreen onTab={handleTab} isDark={isDark} setIsDark={setIsDark} />
        ) : null
      )}
    </div>
  );
}
