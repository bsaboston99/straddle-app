import { IconList, IconBarChart, IconCalendar, IconSettings } from "./Icons";

const TABS = [
  { label: "Watchlist", Icon: IconList },
  { label: "Analysis",  Icon: IconBarChart },
  { label: "Earnings",  Icon: IconCalendar },
  { label: "Settings",  Icon: IconSettings },
];

export default function TabBar({ active, onTab }) {
  return (
    <div className="safe-bottom" style={{ display: "flex", borderTop: "0.5px solid var(--border)", background: "var(--surface)", flexShrink: 0 }}>
      {TABS.map(({ label, Icon }) => {
        const isActive = active === label;
        const color = isActive ? "var(--blue)" : "var(--text4)";
        return (
          <div
            key={label}
            onClick={() => onTab(label)}
            style={{
              flex: 1, display: "flex", flexDirection: "column", alignItems: "center",
              padding: "10px 0 12px", gap: 4, cursor: "pointer",
              fontFamily: "system-ui, sans-serif"
            }}
          >
            {isActive && (
              <div style={{ height: 2, background: "var(--blue)", width: 24, borderRadius: 2, marginBottom: 2 }} />
            )}
            <Icon size={20} color={color} />
            <span style={{ fontSize: 10, color }}>{label}</span>
          </div>
        );
      })}
    </div>
  );
}
