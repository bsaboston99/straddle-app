import { useState, useEffect } from "react";
import WatchlistScreen from "./components/WatchlistScreen";
import DetailScreen from "./components/DetailScreen";
import EarningsScreen from "./components/EarningsScreen";
import { API_BASE } from "./data/tickers";

export default function App() {
  const [selected, setSelected] = useState(null);
  const [activeTab, setActiveTab] = useState("Watchlist");
  const [earningsMap, setEarningsMap] = useState({});

  useEffect(() => {
    fetch(`${API_BASE}/earnings?universe=all&weeks=12`)
      .then(r => r.json())
      .then(d => {
        const map = {};
        Object.values(d.grouped).forEach(items => {
          items.forEach(item => {
            map[item.ticker] = { date: item.date, time: item.time };
          });
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
    <div style={{ maxWidth: 390, margin: "0 auto", minHeight: "100vh", display: "flex", flexDirection: "column", borderLeft: "0.5px solid #eee", borderRight: "0.5px solid #eee" }}>
      {selected ? (
        <DetailScreen sym={selected} onBack={() => setSelected(null)} onTab={handleTab} earningsMap={earningsMap} />
      ) : activeTab === "Watchlist" ? (
        <WatchlistScreen onSelectTicker={setSelected} onTab={handleTab} earningsMap={earningsMap} />
      ) : activeTab === "Earnings" ? (
        <EarningsScreen onTab={handleTab} />
      ) : activeTab === "Analysis" ? (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "system-ui, sans-serif", color: "#aaa", fontSize: 14 }}>
          Analysis tab — coming soon
        </div>
      ) : (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "system-ui, sans-serif", color: "#aaa", fontSize: 14 }}>
          Settings tab — coming soon
        </div>
      )}
    </div>
  );
}