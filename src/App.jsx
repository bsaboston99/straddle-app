import { useState, useEffect } from "react";
import WatchlistScreen from "./components/WatchlistScreen";
import AnalysisDetailScreen from "./components/AnalysisDetailScreen";
import EarningsScreen from "./components/EarningsScreen";
import AnalysisScreen from "./components/AnalysisScreen";
import SettingsScreen from "./components/SettingsScreen";
import SplashScreen from "./components/SplashScreen";
import { API_BASE } from "./data/tickers";

export default function App() {
  const [selected, setSelected] = useState(null);
  const [activeTab, setActiveTab] = useState("Watchlist");
  const [earningsMap, setEarningsMap] = useState({});
  const [showSplash, setShowSplash] = useState(true);
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

  function handleTab(tab) {
    setSelected(null);
    setActiveTab(tab);
  }

  return (
    <div style={{
      maxWidth: 430, margin: "0 auto", height: "100dvh", overflow: "hidden",
      display: "flex", flexDirection: "column",
      borderLeft: "0.5px solid var(--border)", borderRight: "0.5px solid var(--border)",
      background: "var(--bg)"
    }}>
      {showSplash && <SplashScreen onComplete={() => setShowSplash(false)} />}

      {selected ? (
        <AnalysisDetailScreen ticker={selected} onBack={() => setSelected(null)} onTab={handleTab} />
      ) : activeTab === "Watchlist" ? (
        <WatchlistScreen onSelectTicker={setSelected} onTab={handleTab} earningsMap={earningsMap} />
      ) : activeTab === "Earnings" ? (
        <EarningsScreen onTab={handleTab} />
      ) : activeTab === "Analysis" ? (
        <AnalysisScreen onTab={handleTab} />
      ) : activeTab === "Settings" ? (
        <SettingsScreen onTab={handleTab} isDark={isDark} setIsDark={setIsDark} />
      ) : null}
    </div>
  );
}
