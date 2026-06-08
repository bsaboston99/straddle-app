export default function TabBar({ active, onTab }) {
  return (
    <div className="safe-bottom" style={{ display: "flex", borderTop: "0.5px solid var(--border)", background: "var(--surface)", flexShrink: 0 }}>
      {[["☰", "Watchlist"], ["📊", "Analysis"], ["📅", "Earnings"], ["⚙️", "Settings"]].map(([icon, label]) => (
        <div
          key={label}
          onClick={() => onTab(label)}
          style={{
            flex: 1, display: "flex", flexDirection: "column", alignItems: "center",
            padding: "10px 0 12px", gap: 4, cursor: "pointer",
            color: active === label ? "var(--text)" : "var(--text4)", fontSize: 10,
            fontFamily: "system-ui, sans-serif"
          }}
        >
          {active === label && (
            <div style={{ height: 2, background: "var(--blue)", width: 24, borderRadius: 2, marginBottom: 2 }} />
          )}
          <span style={{ fontSize: 20 }}>{icon}</span>
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}
