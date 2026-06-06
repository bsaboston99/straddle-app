import { useState } from "react";
import WatchlistScreen from "./components/WatchlistScreen";
import DetailScreen from "./components/DetailScreen";
import EarningsScreen from "./components/EarningsScreen";

export default function App() {
  const [selected, setSelected] = useState(null);
  const [activeTab, setActiveTab] = useState("Watchlist");

  function handleTab(tab) {
    setSelected(null);
    setActiveTab(tab);
  }

  if (selected) {
    return (
      <div style={{ maxWidth: 390, margin: "0 auto", minHeight: "100vh", display: "flex", flexDirection: "column", borderLeft: "0.5px solid #eee", borderRight: "0.5px solid #eee" }}>
        <DetailScreen sym={selected} onBack={() => setSelected(null)} onTab={handleTab} />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 390, margin: "0 auto", minHeight: "100vh", display: "flex", flexDirection: "column", borderLeft: "0.5px solid #eee", borderRight: "0.5px solid #eee" }}>
      {activeTab === "Watchlist" && <WatchlistScreen onSelectTicker={setSelected} onTab={handleTab} />}
      {activeTab === "Earnings" && <EarningsScreen onTab={handleTab} />}
      {activeTab === "Analysis" && (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "system-ui, sans-serif", color: "#aaa", fontSize: 14 }}>
          Analysis tab — coming soon
        </div>
      )}
      {activeTab === "Settings" && (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "system-ui, sans-serif", color: "#aaa", fontSize: 14 }}>
          Settings tab — coming soon
        </div>
      )}
    </div>
  );
}