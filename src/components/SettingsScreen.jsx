import { useState, useEffect } from "react";
import TabBar from "./TabBar";

function Toggle({ value, onChange }) {
  return (
    <div
      onClick={() => onChange(!value)}
      style={{
        width: 51, height: 31, borderRadius: 16,
        background: value ? "var(--blue)" : "var(--border)",
        position: "relative", cursor: "pointer",
        transition: "background 0.2s", flexShrink: 0
      }}
    >
      <div style={{
        position: "absolute",
        top: 2, left: value ? 22 : 2,
        width: 27, height: 27, borderRadius: "50%",
        background: "#fff",
        transition: "left 0.2s",
        boxShadow: "0 1px 4px rgba(0,0,0,0.35)"
      }} />
    </div>
  );
}

function SectionHeader({ label }) {
  return (
    <div style={{ padding: "20px 20px 6px", fontSize: 11, fontWeight: 600, color: "var(--text3)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
      {label}
    </div>
  );
}

export default function SettingsScreen({ onTab, isDark, setIsDark }) {
  const [alertsEnabled, setAlertsEnabled] = useState(() => {
    try { return localStorage.getItem("alerts_enabled") === "true"; }
    catch { return false; }
  });
  const [threshold, setThreshold] = useState(() => {
    try { return Number(localStorage.getItem("alerts_threshold") || "25"); }
    catch { return 25; }
  });

  useEffect(() => {
    try { localStorage.setItem("alerts_enabled", String(alertsEnabled)); } catch {}
  }, [alertsEnabled]);

  useEffect(() => {
    try { localStorage.setItem("alerts_threshold", String(threshold)); } catch {}
  }, [threshold]);

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, fontFamily: "system-ui, sans-serif", background: "var(--bg)", overflow: "hidden" }}>

      {/* Header */}
      <div style={{ padding: "18px 20px 14px", borderBottom: "0.5px solid var(--border)", flexShrink: 0 }}>
        <h1 style={{ fontSize: 20, fontWeight: 500, margin: 0, color: "var(--text)" }}>Settings</h1>
      </div>

      <div style={{ flex: 1, overflowY: "auto", paddingBottom: 20 }}>

        {/* Appearance */}
        <SectionHeader label="Appearance" />
        <div style={{ margin: "0 16px", background: "var(--surface)", borderRadius: 12, overflow: "hidden" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 16px" }}>
            <div>
              <div style={{ fontSize: 15, color: "var(--text)" }}>Dark Mode</div>
              <div style={{ fontSize: 12, color: "var(--text3)", marginTop: 2 }}>
                {isDark ? "Dark theme active" : "Light theme active"}
              </div>
            </div>
            <Toggle value={isDark} onChange={setIsDark} />
          </div>
        </div>

        {/* Alerts */}
        <SectionHeader label="Alerts" />
        <div style={{ margin: "0 16px", background: "var(--surface)", borderRadius: 12, overflow: "hidden" }}>

          {/* Enable toggle */}
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "14px 16px",
            borderBottom: alertsEnabled ? "0.5px solid var(--border)" : "none"
          }}>
            <div>
              <div style={{ fontSize: 15, color: "var(--text)" }}>Enable Alerts</div>
              <div style={{ fontSize: 12, color: "var(--text3)", marginTop: 2 }}>
                {alertsEnabled ? "Alerts are active" : "Alerts are off"}
              </div>
            </div>
            <Toggle value={alertsEnabled} onChange={setAlertsEnabled} />
          </div>

          {/* Threshold slider — only shown when alerts are on */}
          {alertsEnabled && (
            <div style={{ padding: "14px 16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
                <div style={{ fontSize: 15, color: "var(--text)" }}>EP Percentile Threshold</div>
                <div style={{ fontSize: 20, fontWeight: 500, color: "var(--blue)" }}>{threshold}th</div>
              </div>
              <input
                type="range"
                min={0} max={100} value={threshold}
                onChange={e => setThreshold(Number(e.target.value))}
                style={{ width: "100%", accentColor: "var(--blue)", cursor: "pointer" }}
              />
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--text4)", marginTop: 6 }}>
                <span>0th</span>
                <span>25th</span>
                <span>50th</span>
                <span>75th</span>
                <span>100th</span>
              </div>
              <div style={{ fontSize: 12, color: "var(--text3)", marginTop: 10, lineHeight: 1.5 }}>
                You'll be notified when any watchlist ticker's earnings premium drops below the <strong style={{ color: "var(--text2)" }}>{threshold}th percentile</strong>.
              </div>
            </div>
          )}
        </div>

        {/* Info note */}
        <div style={{
          margin: "10px 16px 0",
          padding: "12px 14px",
          background: "var(--surface)", borderRadius: 12,
          display: "flex", gap: 10, alignItems: "flex-start"
        }}>
          <span style={{ fontSize: 16, flexShrink: 0 }}>ℹ️</span>
          <div style={{ fontSize: 12, color: "var(--text3)", lineHeight: 1.55 }}>
            Alerts will notify you when any watchlist ticker's earnings premium percentile crosses below your threshold — a signal that the market is pricing in a relatively cheap earnings move. Push notification delivery coming soon.
          </div>
        </div>

      </div>

      <TabBar active="Settings" onTab={onTab} />
    </div>
  );
}
