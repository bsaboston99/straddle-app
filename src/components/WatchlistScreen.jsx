import { tickers } from "../data/tickers";
import { MiniBar } from "./MiniBar";
import TabBar from "./TabBar";

const upColor = "#3B6D11", downColor = "#A32D2D";
const upBg = "#EAF3DE", downBg = "#FCEBEB";

const US_HOLIDAYS = new Set([
  "2026-01-01","2026-01-19","2026-02-16","2026-04-03","2026-05-25",
  "2026-07-03","2026-09-07","2026-11-26","2026-12-25",
  "2027-01-01","2027-01-18","2027-02-15","2027-04-02","2027-05-31",
  "2027-07-05","2027-09-06","2027-11-25","2027-12-24",
]);

function isNonTradingDay(date) {
  const day = date.getDay();
  if (day === 0 || day === 6) return true;
  const str = date.toISOString().split("T")[0];
  return US_HOLIDAYS.has(str);
}

function tradingDaysUntil(dateStr, time) {
  if (!dateStr) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const earnDate = new Date(dateStr + "T00:00:00");

  const lastDayToAct = new Date(earnDate);
  if (time === "BMO") {
    lastDayToAct.setDate(lastDayToAct.getDate() - 1);
    while (isNonTradingDay(lastDayToAct)) {
      lastDayToAct.setDate(lastDayToAct.getDate() - 1);
    }
  }

  const startDay = new Date(today);
  while (isNonTradingDay(startDay)) {
    startDay.setDate(startDay.getDate() + 1);
  }

  let count = 0;
  const cursor = new Date(startDay);
  while (cursor <= lastDayToAct) {
    if (!isNonTradingDay(cursor)) count++;
    cursor.setDate(cursor.getDate() + 1);
  }

  if (count <= 0) return "Reported";
  if (time === "BMO") {
    const daysLeft = count - 1;
    if (daysLeft === 0) return "0 Days Before Earnings";
    return `${daysLeft} Day${daysLeft !== 1 ? "s" : ""} Before Earnings`;
  }
  if (count === 0) return "0 Days Before Earnings";
  return `${count} Day${count !== 1 ? "s" : ""} Before Earnings`;
}

function tradingDaysCount(dateStr, time) {
  if (!dateStr) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const earnDate = new Date(dateStr + "T00:00:00");

  const lastDayToAct = new Date(earnDate);
  if (time === "BMO") {
    lastDayToAct.setDate(lastDayToAct.getDate() - 1);
    while (isNonTradingDay(lastDayToAct)) {
      lastDayToAct.setDate(lastDayToAct.getDate() - 1);
    }
  }

  const startDay = new Date(today);
  while (isNonTradingDay(startDay)) {
    startDay.setDate(startDay.getDate() + 1);
  }

  let count = 0;
  const cursor = new Date(startDay);
  while (cursor <= lastDayToAct) {
    if (!isNonTradingDay(cursor)) count++;
    cursor.setDate(cursor.getDate() + 1);
  }

  return time === "BMO" ? count - 1 : count;
}

function earnBadgeDate(dateStr) {
  if (!dateStr) return null;
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function TickerRow({ sym, onClick, earningsMap }) {
  const t = tickers[sym];
  const isUp = t.dir === "up";
  const earnInfo = earningsMap[sym] || null;
  const badge = earnInfo ? earnBadgeDate(earnInfo.date) : null;
  const subLabel = earnInfo
    ? tradingDaysUntil(earnInfo.date, earnInfo.time)
    : "Date TBD";

  return (
    <div
      onClick={onClick}
      style={{
        display: "grid", gridTemplateColumns: "1fr 70px 64px 80px",
        alignItems: "center", padding: "11px 16px", gap: 6,
        borderBottom: "0.5px solid #eee", cursor: "pointer"
      }}
    >
      <div>
        <div style={{ fontSize: 15, fontWeight: 500 }}>
          {sym}
          {badge && (
            <span style={{ background: "#FAEEDA", color: "#854F0B", fontSize: 10, padding: "1px 5px", borderRadius: 4, marginLeft: 4, fontWeight: 500 }}>
              {badge}
            </span>
          )}
        </div>
        <div style={{ fontSize: 11, color: "#aaa", marginTop: 2 }}>{subLabel}</div>
        <div style={{ marginTop: 6, width: 90 }}>
          <MiniBar pct={t.pct_a} sig={t.sig_a} label="A" />
          <MiniBar pct={t.pct_b} sig={t.sig_b} label="B" />
          <MiniBar pct={t.pct_ep} sig={t.sig_ep} label="EP" />
        </div>
      </div>
      <div style={{ textAlign: "right", fontSize: 13, fontWeight: 500 }}>{t.price}</div>
      <div style={{ textAlign: "right" }}>
        <span style={{
          background: isUp ? upBg : downBg,
          color: isUp ? upColor : downColor,
          fontSize: 11, fontWeight: 500, padding: "2px 5px", borderRadius: 4
        }}>
          {t.change}
        </span>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ fontSize: 13, fontWeight: 500 }}>{t.front}</div>
        <div style={{ fontSize: 10, color: "#aaa", marginTop: 1 }}>{t.frontPct}</div>
      </div>
    </div>
  );
}

export default function WatchlistScreen({ onSelectTicker, onTab, earningsMap }) {
  const allSyms = Object.keys(tickers);

  const thisWeek = [];
  const nextWeek = [];
  const upcoming = [];
  const noDate = [];

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const dayOfWeek = today.getDay();
  const monday = new Date(today);
  monday.setDate(today.getDate() - (dayOfWeek === 0 ? 6 : dayOfWeek - 1));
  const friday = new Date(monday);
  friday.setDate(monday.getDate() + 4);
  const nextMonday = new Date(monday);
  nextMonday.setDate(monday.getDate() + 7);
  const nextFriday = new Date(nextMonday);
  nextFriday.setDate(nextMonday.getDate() + 4);

  allSyms.forEach(sym => {
    const earnInfo = earningsMap[sym];
    if (!earnInfo) {
      noDate.push({ sym, date: null });
      return;
    }
    const earnDate = new Date(earnInfo.date + "T00:00:00");
    const days = tradingDaysCount(earnInfo.date, earnInfo.time);
    if (days !== null && days < 0) {
      noDate.push({ sym, date: earnDate });
    } else if (earnDate >= monday && earnDate <= friday) {
      thisWeek.push({ sym, date: earnDate, days });
    } else if (earnDate >= nextMonday && earnDate <= nextFriday) {
      nextWeek.push({ sym, date: earnDate, days });
    } else if (earnDate > nextFriday) {
      upcoming.push({ sym, date: earnDate, days });
    } else {
      noDate.push({ sym, date: null });
    }
  });

  thisWeek.sort((a, b) => a.date - b.date);
  nextWeek.sort((a, b) => a.date - b.date);
  upcoming.sort((a, b) => a.date - b.date);

  const SectionHeader = ({ label }) => (
    <div style={{ padding: "10px 16px 4px", fontSize: 12, fontWeight: 500, color: "#888" }}>
      {label}
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, fontFamily: "system-ui, sans-serif" }}>

      <div style={{ padding: "18px 20px 12px", borderBottom: "0.5px solid #eee" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <h1 style={{ fontSize: 20, fontWeight: 500, margin: 0 }}>Watchlist</h1>
          <div style={{ display: "flex", gap: 16, fontSize: 20, color: "#888" }}>
            <span>🔔</span><span>🔍</span>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, background: "#f5f5f3", borderRadius: 8, padding: "8px 12px" }}>
          <span style={{ color: "#aaa", fontSize: 14 }}>🔍</span>
          <span style={{ fontSize: 14, color: "#aaa" }}>Search tickers...</span>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 70px 64px 80px", padding: "8px 16px 6px", gap: 6 }}>
        {["Ticker / Percentiles", "Price", "Chg", "Straddle"].map((h, i) => (
          <span key={h} style={{ fontSize: 10, color: "#aaa", textTransform: "uppercase", letterSpacing: "0.04em", textAlign: i > 0 ? "right" : "left" }}>
            {h}
          </span>
        ))}
      </div>

      <div style={{ flex: 1 }}>
        {thisWeek.length > 0 && (
          <>
            <SectionHeader label="Earnings This Week" />
            {thisWeek.map(({ sym }) => (
              <TickerRow key={sym} sym={sym} onClick={() => onSelectTicker(sym)} earningsMap={earningsMap} />
            ))}
          </>
        )}

        {nextWeek.length > 0 && (
          <>
            <SectionHeader label="Earnings Next Week" />
            {nextWeek.map(({ sym }) => (
              <TickerRow key={sym} sym={sym} onClick={() => onSelectTicker(sym)} earningsMap={earningsMap} />
            ))}
          </>
        )}

        {upcoming.length > 0 && (
          <>
            <SectionHeader label="Upcoming Earnings" />
            {upcoming.map(({ sym }) => (
              <TickerRow key={sym} sym={sym} onClick={() => onSelectTicker(sym)} earningsMap={earningsMap} />
            ))}
          </>
        )}

        {noDate.length > 0 && (
          <>
            <SectionHeader label="Date Not Confirmed" />
            {noDate.map(({ sym }) => (
              <TickerRow key={sym} sym={sym} onClick={() => onSelectTicker(sym)} earningsMap={earningsMap} />
            ))}
          </>
        )}
      </div>

      <TabBar active="Watchlist" onTab={onTab} />
    </div>
  );
}