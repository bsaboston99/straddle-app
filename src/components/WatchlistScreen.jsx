import { useState, useEffect } from "react";
import { API_BASE } from "../data/tickers";
import { MiniBar } from "./MiniBar";
import TabBar from "./TabBar";
import { IconSearch, IconBell } from "./Icons";

const US_HOLIDAYS = new Set([
  "2026-01-01","2026-01-19","2026-02-16","2026-04-03","2026-05-25",
  "2026-07-03","2026-09-07","2026-11-26","2026-12-25",
  "2027-01-01","2027-01-18","2027-02-15","2027-04-02","2027-05-31",
  "2027-07-05","2027-09-06","2027-11-25","2027-12-24",
]);

function isNonTradingDay(date) {
  const day = date.getDay();
  if (day === 0 || day === 6) return true;
  return US_HOLIDAYS.has(date.toISOString().split("T")[0]);
}

function tradingDaysUntil(dateStr, time) {
  if (!dateStr) return null;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const earnDate = new Date(dateStr + "T00:00:00");
  const lastDayToAct = new Date(earnDate);
  if (time === "BMO") {
    lastDayToAct.setDate(lastDayToAct.getDate() - 1);
    while (isNonTradingDay(lastDayToAct)) lastDayToAct.setDate(lastDayToAct.getDate() - 1);
  }
  const startDay = new Date(today);
  while (isNonTradingDay(startDay)) startDay.setDate(startDay.getDate() + 1);
  let count = 0;
  const cursor = new Date(startDay);
  while (cursor <= lastDayToAct) {
    if (!isNonTradingDay(cursor)) count++;
    cursor.setDate(cursor.getDate() + 1);
  }
  if (count <= 0) return "Reported";
  if (time === "BMO") {
    const d = count - 1;
    if (d === 0) return "0 Days Before Earnings";
    return `${d} Day${d !== 1 ? "s" : ""} Before Earnings`;
  }
  if (count === 0) return "0 Days Before Earnings";
  return `${count} Day${count !== 1 ? "s" : ""} Before Earnings`;
}

function tradingDaysCount(dateStr, time) {
  if (!dateStr) return null;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const earnDate = new Date(dateStr + "T00:00:00");
  const lastDayToAct = new Date(earnDate);
  if (time === "BMO") {
    lastDayToAct.setDate(lastDayToAct.getDate() - 1);
    while (isNonTradingDay(lastDayToAct)) lastDayToAct.setDate(lastDayToAct.getDate() - 1);
  }
  const startDay = new Date(today);
  while (isNonTradingDay(startDay)) startDay.setDate(startDay.getDate() + 1);
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
  return new Date(dateStr + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function TickerRow({ sym, onClick, earningsMap, live }) {
  const earnInfo = earningsMap[sym] || null;
  const badge = earnInfo ? earnBadgeDate(earnInfo.date) : null;
  const subLabel = earnInfo ? tradingDaysUntil(earnInfo.date, earnInfo.time) : "Date TBD";

  const hasPrice    = live && live.price != null;
  const hasChange   = live && live.change_pct != null;
  const hasStraddle = live && live.straddle_dollar != null && live.straddle_pct != null;
  const hasPct      = live && live.pct_a != null;
  const isUp        = hasChange ? live.change_pct >= 0 : null;

  const priceLabel    = hasPrice    ? `$${live.price.toFixed(2)}`                        : "—";
  const changeLabel   = hasChange   ? `${isUp ? "+" : ""}${live.change_pct.toFixed(2)}%`  : "—";
  const frontLabel    = hasStraddle ? `$${live.straddle_dollar.toFixed(2)}`               : "—";
  const frontPctLabel = hasStraddle ? `${(live.straddle_pct * 100).toFixed(2)}% of price` : "Loading…";

  return (
    <div onClick={onClick} style={{
      display: "grid", gridTemplateColumns: "1fr 70px 64px 80px",
      alignItems: "center", padding: "11px 16px", gap: 6,
      borderBottom: "0.5px solid var(--border)", cursor: "pointer"
    }}>
      <div>
        <div style={{ fontSize: 15, fontWeight: 500, color: "var(--text)" }}>
          {sym}
          {badge && (
            <span style={{ background: "var(--earn-bg)", color: "var(--earn-text)", fontSize: 10, padding: "1px 5px", borderRadius: 4, marginLeft: 4, fontWeight: 500 }}>
              {badge}
            </span>
          )}
        </div>
        <div style={{ fontSize: 11, color: "var(--text3)", marginTop: 2 }}>{subLabel}</div>
        {hasPct ? (
          <div style={{ marginTop: 6, width: 90 }}>
            <MiniBar pct={live.pct_a}  sig={live.signal_a}  label="A" />
            <MiniBar pct={live.pct_b}  sig={live.signal_b}  label="B" />
            <MiniBar pct={live.pct_ep} sig={live.signal_ep} label="EP" />
          </div>
        ) : (
          <div style={{ marginTop: 6, fontSize: 10, color: "var(--text4)" }}>Loading percentiles…</div>
        )}
      </div>
      <div style={{ textAlign: "right", fontSize: 13, fontWeight: 500, color: "var(--text)" }}>{priceLabel}</div>
      <div style={{ textAlign: "right" }}>
        <span style={{
          background: isUp === null ? "var(--border)" : isUp ? "var(--up-bg)" : "var(--down-bg)",
          color: isUp === null ? "var(--text3)" : isUp ? "var(--up)" : "var(--down)",
          fontSize: 11, fontWeight: 500, padding: "2px 5px", borderRadius: 4
        }}>
          {changeLabel}
        </span>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text)" }}>{frontLabel}</div>
        <div style={{ fontSize: 10, color: "var(--text3)", marginTop: 1 }}>{frontPctLabel}</div>
      </div>
    </div>
  );
}

function Spinner() {
  return (
    <>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", flex: 1, gap: 12 }}>
        <div style={{
          width: 24, height: 24, borderRadius: "50%",
          border: "2px solid var(--border)",
          borderTopColor: "var(--blue)",
          animation: "spin 0.75s linear infinite"
        }} />
        <div style={{ fontSize: 12, color: "var(--text3)" }}>Loading tickers…</div>
      </div>
    </>
  );
}

export default function WatchlistScreen({ onSelectTicker, onTab, earningsMap }) {
  const [searchQuery, setSearchQuery] = useState("");
  const [allSyms, setAllSyms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [liveData, setLiveData] = useState({});

  useEffect(() => {
    fetch(`${API_BASE}/analysis?dbe=0`)
      .then(r => r.json())
      .then(d => {
        setAllSyms((d.tickers || []).map(t => t.ticker));
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  // Live price/change/percentile data for every row -- fetched separately
  // from the ticker list above since it hits Alpaca per ticker and takes
  // longer; rows render with a "Loading…" state until this resolves, then
  // re-render once. Refreshed every 60s to match the backend's cache TTL.
  useEffect(() => {
    let cancelled = false;
    const loadLive = () => {
      fetch(`${API_BASE}/watchlist-live`)
        .then(r => r.json())
        .then(d => { if (!cancelled) setLiveData(d.tickers || {}); })
        .catch(() => {});
    };
    loadLive();
    const interval = setInterval(loadLive, 60000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  const query = searchQuery.trim().toUpperCase();
  const searchResults = query
    ? allSyms.filter(sym => sym.includes(query))
    : null;

  const thisWeek = [], nextWeek = [], upcoming = [], noDate = [];
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const dayOfWeek = today.getDay();
  const monday = new Date(today); monday.setDate(today.getDate() - (dayOfWeek === 0 ? 6 : dayOfWeek - 1));
  const friday = new Date(monday); friday.setDate(monday.getDate() + 4);
  const nextMonday = new Date(monday); nextMonday.setDate(monday.getDate() + 7);
  const nextFriday = new Date(nextMonday); nextFriday.setDate(nextMonday.getDate() + 4);

  allSyms.forEach(sym => {
    const earnInfo = earningsMap[sym];
    if (!earnInfo) { noDate.push({ sym, date: null }); return; }
    const earnDate = new Date(earnInfo.date + "T00:00:00");
    const days = tradingDaysCount(earnInfo.date, earnInfo.time);
    if (days !== null && days < 0)                               noDate.push({ sym, date: earnDate });
    else if (earnDate >= monday && earnDate <= friday)           thisWeek.push({ sym, date: earnDate, days });
    else if (earnDate >= nextMonday && earnDate <= nextFriday)   nextWeek.push({ sym, date: earnDate, days });
    else if (earnDate > nextFriday)                              upcoming.push({ sym, date: earnDate, days });
    else                                                         noDate.push({ sym, date: null });
  });

  thisWeek.sort((a, b) => a.date - b.date);
  nextWeek.sort((a, b) => a.date - b.date);
  upcoming.sort((a, b) => a.date - b.date);

  const SectionHeader = ({ label }) => (
    <div style={{ padding: "10px 16px 4px", fontSize: 12, fontWeight: 500, color: "var(--text3)" }}>
      {label}
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, fontFamily: "system-ui, sans-serif", background: "var(--bg)", overflow: "hidden" }}>

      <div className="safe-top" style={{ padding: "18px 20px 12px", borderBottom: "0.5px solid var(--border)", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <h1 style={{ fontSize: 20, fontWeight: 500, margin: 0, color: "var(--text)" }}>Watchlist</h1>
          <div style={{ display: "flex", gap: 16, color: "var(--text4)" }}>
            <IconBell size={20} /><IconSearch size={20} />
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, background: "var(--surface)", borderRadius: 8, padding: "8px 12px" }}>
          <IconSearch size={15} color="var(--text4)" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search tickers..."
            autoCapitalize="characters"
            autoCorrect="off"
            spellCheck={false}
            style={{ flex: 1, fontSize: 14, color: "var(--text)", background: "none", border: "none", outline: "none" }}
          />
          {searchQuery && (
            <span onClick={() => setSearchQuery("")} style={{ color: "var(--text4)", fontSize: 16, cursor: "pointer", padding: "0 2px", lineHeight: 1 }}>×</span>
          )}
        </div>
      </div>

      {!loading && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 70px 64px 80px", padding: "8px 16px 6px", gap: 6, flexShrink: 0 }}>
          {["Ticker / Percentiles", "Price", "Chg", "Straddle"].map((h, i) => (
            <span key={h} style={{ fontSize: 10, color: "var(--text4)", textTransform: "uppercase", letterSpacing: "0.04em", textAlign: i > 0 ? "right" : "left" }}>
              {h}
            </span>
          ))}
        </div>
      )}

      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column" }}>
        {loading ? <Spinner /> : searchResults ? (
          searchResults.length === 0 ? (
            <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--text3)", fontSize: 13 }}>
              No results for "{searchQuery}"
            </div>
          ) : (
            <>
              <SectionHeader label={`${searchResults.length} result${searchResults.length !== 1 ? "s" : ""}`} />
              {searchResults.map(sym => (
                <TickerRow key={sym} sym={sym} onClick={() => onSelectTicker(sym)} earningsMap={earningsMap} live={liveData[sym]} />
              ))}
            </>
          )
        ) : (
          <>
            {thisWeek.length > 0 && (<>
              <SectionHeader label="Earnings This Week" />
              {thisWeek.map(({ sym }) => <TickerRow key={sym} sym={sym} onClick={() => onSelectTicker(sym)} earningsMap={earningsMap} live={liveData[sym]} />)}
            </>)}
            {nextWeek.length > 0 && (<>
              <SectionHeader label="Earnings Next Week" />
              {nextWeek.map(({ sym }) => <TickerRow key={sym} sym={sym} onClick={() => onSelectTicker(sym)} earningsMap={earningsMap} live={liveData[sym]} />)}
            </>)}
            {upcoming.length > 0 && (<>
              <SectionHeader label="Upcoming Earnings" />
              {upcoming.map(({ sym }) => <TickerRow key={sym} sym={sym} onClick={() => onSelectTicker(sym)} earningsMap={earningsMap} live={liveData[sym]} />)}
            </>)}
            {noDate.length > 0 && (<>
              <SectionHeader label="Date Not Confirmed" />
              {noDate.map(({ sym }) => <TickerRow key={sym} sym={sym} onClick={() => onSelectTicker(sym)} earningsMap={earningsMap} live={liveData[sym]} />)}
            </>)}
          </>
        )}
      </div>

      <TabBar active="Watchlist" onTab={onTab} />
    </div>
  );
}
