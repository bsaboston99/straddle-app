export default function TabBar({ active, onTab }) {
  return (
    <div style={{ display: "flex", borderTop: "0.5px solid #eee", background: "#fff" }}>
      {[["☰", "Watchlist"], ["📊", "Analysis"], ["📅", "Earnings"], ["⚙️", "Settings"]].map(([icon, label]) => (
        <div
          key={label}
          onClick={() => onTab(label)}
          style={{
            flex: 1, display: "flex", flexDirection: "column", alignItems: "center",
            padding: "10px 0 12px", gap: 4, cursor: "pointer",
            color: active === label ? "#111" : "#aaa", fontSize: 10
          }}
        >
          {active === label && (
            <div style={{ height: 2, background: "#111", width: 24, borderRadius: 2, marginBottom: 2 }} />
          )}
          <span style={{ fontSize: 20 }}>{icon}</span>
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}