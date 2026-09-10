from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import pandas as pd
import os
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from straddle_analysis import load_all_data, add_relative_straddles, get_straddle_percentile, get_straddle_percentile_live
import paper_trading
import live_quotes

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Local override via env var; defaults to data/combined_daily relative to this file
COMBINED_DIR = Path(os.environ.get(
    "COMBINED_DIR",
    Path(__file__).parent / "data" / "combined_daily"
))

df_global = None

# Per-ticker ROW POSITIONS into df_global (not copies of the rows
# themselves), rebuilt alongside it. Endpoints that loop over many tickers
# (like /watchlist-live) use this to slice df_global.iloc[...] on demand
# instead of re-scanning the full 80k+-row df_global once per ticker.
#
# This used to be {ticker: sub-DataFrame} -- a dict comprehension over
# df_global.groupby("ticker"), which materializes a full COPY of every row
# in df_global a second time (every row belongs to exactly one ticker
# group, so the copies summed to ~the same size as df_global itself).
# That meant the whole dataset was held in memory TWICE, permanently, for
# the life of the process -- confirmed as a major contributor to
# insignia-api repeatedly hitting Render's 512MB memory limit. Storing
# just the integer positions (a handful of int64s per ticker, ~1MB total
# vs. tens-to-hundreds of MB) gets the same "skip re-scanning df_global"
# benefit at the call site without permanently duplicating the data.
TICKER_GROUPS = {}

FEATHER_CACHE = Path(__file__).parent / "df_cache.feather"

def _get_parquet_mtime() -> float:
    """Return the newest mtime across all parquet files in COMBINED_DIR."""
    try:
        mtimes = [p.stat().st_mtime for p in COMBINED_DIR.glob("*.parquet")]
        return max(mtimes) if mtimes else 0.0
    except Exception:
        return 0.0

def _load_df() -> "pd.DataFrame | None":
    """Load processed DataFrame from feather cache if fresh, else rebuild from parquet."""
    # Check if feather cache exists and is newer than all source parquet files
    if FEATHER_CACHE.exists():
        try:
            cache_mtime = FEATHER_CACHE.stat().st_mtime
            if cache_mtime >= _get_parquet_mtime():
                print("Loading DataFrame from feather cache...")
                df = pd.read_feather(FEATHER_CACHE)
                print(f"Feather cache loaded. {len(df):,} rows.")
                return df
            else:
                print("Parquet files newer than cache — rebuilding.")
        except Exception as e:
            print(f"Feather cache read error: {e} — rebuilding.")

    # Build from source parquet files
    print("Loading parquet files...")
    df = load_all_data(COMBINED_DIR)
    df = add_relative_straddles(df)
    print(f"Parquet loaded. {len(df):,} rows. Saving feather cache...")

    try:
        df.reset_index(drop=True).to_feather(FEATHER_CACHE)
        print("Feather cache saved.")
    except Exception as e:
        print(f"Feather cache write error (non-fatal): {e}")

    return df

@app.on_event("startup")
async def startup_event():
    global df_global, TICKER_GROUPS
    try:
        df_global = _load_df()
        # .indices (not .groups) -- returns {ticker: ndarray of integer row
        # positions}, suitable for df_global.iloc[...]. This is the piece
        # that avoids duplicating df_global's data; see the TICKER_GROUPS
        # comment above.
        TICKER_GROUPS = df_global.groupby("ticker", sort=False).indices
    except Exception as e:
        print(f"WARNING: Could not load data: {e}")
        df_global = None

    try:
        paper_trading.init_db()
    except Exception as e:
        print(f"WARNING: Could not init paper trading db: {e}")

    # Pre-warm earnings cache in background so first user doesn't wait
    asyncio.create_task(_prewarm_earnings())

    # Pre-warm (and keep warm) the Watchlist live-data cache the same way,
    # so a user opening the Watchlist tab almost always hits the 60s cache
    # instead of triggering the live fetch themselves.
    asyncio.create_task(_prewarm_watchlist_live())

async def _prewarm_earnings():
    await asyncio.sleep(3)  # let server finish starting
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: get_earnings(universe="all", weeks=8))
    print("Earnings pre-warm complete.")


# Trading-hours window for the always-on prewarm loop below. Checked in ET
# (not UTC, not the server's local time) via zoneinfo so it stays correct
# across the EST/EDT changeover with no manual adjustment. There's no need
# to keep the ThreadPoolExecutor/Alpaca-call/DataFrame-copy churn of
# get_watchlist_live() running overnight and on weekend mornings when no
# one's looking at the Watchlist screen -- that loop was found to be the
# single biggest steady-state contributor to insignia-api's memory usage
# (every ~55s, 24/7, regardless of market hours), so gating it here directly
# addresses that instead of just reducing its frequency.
PREWARM_TZ = ZoneInfo("America/New_York")
PREWARM_START_HOUR = 9   # 9am ET
PREWARM_END_HOUR = 17    # 5pm ET (exclusive)

def _within_prewarm_window() -> bool:
    now_et = datetime.now(PREWARM_TZ)
    return PREWARM_START_HOUR <= now_et.hour < PREWARM_END_HOUR


async def _prewarm_watchlist_live():
    await asyncio.sleep(5)  # let df_global/earnings pre-warm settle first
    loop = asyncio.get_event_loop()
    while True:
        if _within_prewarm_window():
            try:
                await loop.run_in_executor(None, get_watchlist_live)
                print("Watchlist live pre-warm complete.")
            except Exception as e:
                print(f"Watchlist live pre-warm failed: {e}")
            # Refresh a few seconds before the cache would otherwise expire,
            # so there's effectively never a cold cache for a real request
            # to hit during trading hours.
            await asyncio.sleep(max(WATCHLIST_LIVE_TTL_SECONDS - 5, 5))
        else:
            # Outside 9am-5pm ET: do no work at all (no thread pool, no
            # Alpaca calls, no DataFrame copies) and just recheck
            # periodically so the loop picks back up promptly once the
            # window opens. A real user opening the Watchlist screen
            # off-hours still gets a live (uncached) result -- this only
            # stops the *automatic* background refresh, per get_watchlist_live
            # itself, which is unaffected by this gate.
            await asyncio.sleep(300)

SP500 = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","BRK-B","JPM","UNH",
    "XOM","LLY","JNJ","V","PG","MA","HD","CVX","MRK","ABBV","PEP","COST",
    "ADBE","CRM","TMO","BAC","ACN","MCD","QCOM","NKE","TXN","AMD","PM","DHR",
    "ORCL","WMT","AVGO","CAT","GS","RTX","HON","AMGN","LMT","SBUX","GILD",
    "MDLZ","AXP","ISRG","BKNG","NOW","PANW","LRCX","ADI","KLAC","SNPS","CDNS"
]

NASDAQ100_EXTRA = [
    "ASML","MELI","ABNB","CRWD","DXCM","FANG","FTNT","IDXX","ILMN","KDP",
    "LCID","LULU","MAR","MRNA","MTCH","MU","NFLX","ODFL","ON","PAYX","PCAR",
    "PDD","REGN","RIVN","ROST","TEAM","TTD","VRSK","VRTX","WDAY","ZM","ZS"
]

HIGH_VOL_OPTIONS = [
    "SPY","QQQ","IWM","GLD","SLV","TLT","XLE","XLF","XLK","ARKK",
    "BABA","NFLX","SNAP","UBER","LYFT","COIN","HOOD","PLTR","RBLX","SOFI",
    "AMC","GME","MARA","RIOT","SNDL","TLRY","CGC"
]

cache = {}
CACHE_TTL_HOURS = 6

# Disk-based earnings cache — survives process restarts within the same day
EARNINGS_DISK_CACHE = Path(__file__).parent / "earnings_cache.json"

def load_earnings_from_disk() -> dict | None:
    """Return today's cached earnings from disk, or None if stale/missing."""
    try:
        import json
        if not EARNINGS_DISK_CACHE.exists():
            return None
        with open(EARNINGS_DISK_CACHE) as f:
            stored = json.load(f)
        if stored.get("date") == str(datetime.today().date()):
            print("Loaded earnings from disk cache.")
            return stored.get("data")
    except Exception as e:
        print(f"Disk cache read error: {e}")
    return None

def save_earnings_to_disk(data: dict):
    """Write earnings data to disk with today's date stamp."""
    try:
        import json
        payload = {"date": str(datetime.today().date()), "data": data}
        with open(EARNINGS_DISK_CACHE, "w") as f:
            json.dump(payload, f)
        print("Earnings saved to disk cache.")
    except Exception as e:
        print(f"Disk cache write error: {e}")

def is_cache_valid(key: str) -> bool:
    if key not in cache:
        return False
    age = datetime.now() - cache[key]["timestamp"]
    return age < timedelta(hours=CACHE_TTL_HOURS)

def get_universe(name: str) -> list:
    if name == "sp500":
        return SP500
    elif name == "nasdaq100":
        return list(set(SP500 + NASDAQ100_EXTRA))
    elif name == "highvol":
        return HIGH_VOL_OPTIONS
    else:
        return list(set(SP500 + NASDAQ100_EXTRA + HIGH_VOL_OPTIONS))

def fetch_nasdaq_earnings(date_str: str) -> list:
    url = f"https://api.nasdaq.com/api/calendar/earnings?date={date_str}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/market-activity/earnings",
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        rows = data.get("data", {}).get("rows", []) or []
        results = []
        for row in rows:
            ticker = row.get("symbol", "").strip()
            name = row.get("name", "").strip()
            time_raw = row.get("time", "").strip()
            if not ticker:
                continue
            if "pre-market" in time_raw.lower():
                time = "BMO"
            elif "after-hours" in time_raw.lower():
                time = "AMC"
            else:
                time = "TBD"
            results.append({"ticker": ticker, "name": name, "time": time, "date": date_str})
        return results
    except Exception:
        return []

@app.get("/")
def root():
    return {
        "status": "Insignia API running",
        "parquet_loaded": df_global is not None,
        "rows": len(df_global) if df_global is not None else 0
    }

@app.get("/earnings")
def get_earnings(universe: str = "all", weeks: int = 4):
    cache_key = f"earnings_{universe}_{weeks}"

    # 1. In-memory cache (fastest)
    if is_cache_valid(cache_key):
        return cache[cache_key]["data"]

    # 2. Disk cache — valid if it was written today
    disk_data = load_earnings_from_disk()
    if disk_data is not None:
        cache[cache_key] = {"data": disk_data, "timestamp": datetime.now()}
        return disk_data

    # 3. Fetch from NASDAQ (once per day)
    universe_tickers = set(get_universe(universe))
    today = datetime.today().date()

    trading_days = [
        str(today + timedelta(days=i))
        for i in range(weeks * 7)
        if (today + timedelta(days=i)).weekday() < 5
    ]

    raw: dict[str, list] = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_date = {executor.submit(fetch_nasdaq_earnings, d): d for d in trading_days}
        for future in as_completed(future_to_date):
            date_str = future_to_date[future]
            try:
                raw[date_str] = future.result()
            except Exception:
                raw[date_str] = []

    grouped = {}
    for date_str in sorted(raw):
        filtered = [r for r in raw[date_str] if r["ticker"] in universe_tickers]
        if filtered:
            grouped[date_str] = filtered

    total = sum(len(v) for v in grouped.values())
    response = {"grouped": grouped, "total": total, "universe": universe}

    # Save to both memory and disk
    cache[cache_key] = {"data": response, "timestamp": datetime.now()}
    save_earnings_to_disk(response)
    return response

def _confirmed_earnings_map(universe: str = "all", weeks: int = 8) -> dict:
    """{ticker: (er_date_str, er_time)} for each ticker's soonest upcoming
    CONFIRMED earnings print within `weeks` -- confirmed meaning NASDAQ's
    calendar reports an actual pre-market ("BMO") or after-hours ("AMC")
    session, not its "time-not-supplied" placeholder (mapped to "TBD" by
    fetch_nasdaq_earnings above) for a date that hasn't been locked in yet.
    Live expiration selection is anchored to this date (see live_quotes.py
    point 5), so a ticker without a confirmed date can't be handled live
    at all -- it's simply left out of this map, and callers fall back to
    the historical calc for it, same as any other live-fetch failure."""
    lookup = {}
    try:
        resp = get_earnings(universe=universe, weeks=weeks)
        dated = []
        for date_str, items in resp.get("grouped", {}).items():
            for item in items:
                if item.get("time") not in ("BMO", "AMC"):
                    continue
                dated.append((date_str, item["ticker"], item["time"]))
        dated.sort(key=lambda x: x[0])
        for d, t, tm in dated:
            if t not in lookup:
                lookup[t] = (d, tm)
    except Exception as e:
        print(f"Confirmed-earnings lookup failed, no tickers will get live data: {e}")
    return lookup


@app.get("/straddle/{ticker}")
def get_straddle(ticker: str, dbe: int = 0):
    if df_global is None:
        raise HTTPException(status_code=503, detail="Parquet data not loaded.")

    cache_key = f"straddle_{ticker.upper()}_{dbe}"
    if is_cache_valid(cache_key):
        return cache[cache_key]["data"]

    sym = ticker.upper()

    try:
        live = None
        confirmed = _confirmed_earnings_map().get(sym)
        if confirmed:
            er_date, er_time = confirmed
            try:
                live = live_quotes.get_live_straddle_inputs(sym, er_date, er_time)
            except Exception as e:
                print(f"Live quote fetch failed for {sym}, falling back to historical: {e}")

        if live:
            result = get_straddle_percentile_live(
                df_global,
                ticker=sym,
                dbe=dbe,
                live_close_a=live["close_a"],
                live_close_b=live["close_b"],
                live_spy_close_a=live["spy_close_a"],
                live_spy_close_b=live["spy_close_b"],
            )
        else:
            result = get_straddle_percentile(df_global, ticker=sym, dbe=dbe)

        response = {
            "is_live":          live is not None,
            "as_of":            datetime.now().isoformat(),
            "ticker":           result["ticker"],
            "dbe":              result["dbe"],
            "pct_a":            result["pct_a"],
            "signal_a":         result["signal_a"],
            "adj_signal_a":     result["adj_signal_a"],
            "pct_b":            result["pct_b"],
            "signal_b":         result["signal_b"],
            "adj_signal_b":     result["adj_signal_b"],
            "pct_ep":           result["pct_ep"],
            "signal_ep":        result["signal_ep"],
            "adj_signal_ep":    result["adj_signal_ep"],
            "composite":        result["composite"],
            "rel_a":            result["rel_a"],
            "rel_b":            result["rel_b"],
            "earnings_premium": result["earnings_premium"],
            "close_a":          result["close_a"],
            "close_b":          result["close_b"],
            "spy_close_a":      result["spy_close_a"],
            "spy_close_b":      result["spy_close_b"],
            "hist_a":           result["hist_a"],
            "hist_b":           result["hist_b"],
            "hist_ep":          result["hist_ep"],
            "spy_a":            result["spy_a"],
            "spy_b":            result["spy_b"],
        }

        cache[cache_key] = {"data": response, "timestamp": datetime.now()}
        return response

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history/{ticker}")
def get_history(ticker: str, dbe: int = 0):
    if df_global is None:
        raise HTTPException(status_code=503, detail="Parquet data not loaded.")

    cache_key = f"history_{ticker.upper()}_{dbe}"
    if is_cache_valid(cache_key):
        return cache[cache_key]["data"]

    sym = ticker.upper()

    ticker_all = df_global[df_global["ticker"] == sym].sort_values("date")

    dbe0 = ticker_all[ticker_all["dbe"] == 0][
        ["date", "er_date", "closestraddle_a", "closestraddle_b",
         "closespystraddle_a", "closespystraddle_b", "stock_close"]
    ].dropna(subset=["closestraddle_a"]).sort_values("date")

    if dbe0.empty:
        raise HTTPException(status_code=404, detail=f"No history for {sym} at DBE=0")

    date_map = {}
    for _, row in ticker_all.iterrows():
        key = str(row["date"])[:10]
        date_map[key] = row

    rows = []
    for _, row in dbe0.iterrows():
        dbe0_date = pd.Timestamp(row["date"])
        er_date_str = str(row["er_date"])[:10]
        stock_close = round(float(row["stock_close"]), 4) if pd.notna(row["stock_close"]) else None

        # Find next trading day
        next_date = dbe0_date + pd.Timedelta(days=1)
        post = None
        for _ in range(7):
            next_key = str(next_date)[:10]
            if next_key in date_map:
                next_row = date_map[next_key]
                post_open  = float(next_row["stock_open"])  if pd.notna(next_row["stock_open"])  else None
                post_close = float(next_row["stock_close"]) if pd.notna(next_row["stock_close"]) else None
                post_straddle_a = round(float(next_row["closestraddle_a"]), 4) if pd.notna(next_row["closestraddle_a"]) else None
                post_straddle_b = round(float(next_row["closestraddle_b"]), 4) if pd.notna(next_row["closestraddle_b"]) else None

                open_chg_pct  = round((post_open  - stock_close) / stock_close * 100, 2) if stock_close and post_open  else None
                close_chg_pct = round((post_close - stock_close) / stock_close * 100, 2) if stock_close and post_close else None

                post = {
                    "stock_open":       round(post_open,  4) if post_open  else None,
                    "stock_close":      round(post_close, 4) if post_close else None,
                    "open_chg_pct":     open_chg_pct,
                    "close_chg_pct":    close_chg_pct,
                    "closestraddle_a":  post_straddle_a,
                    "closestraddle_b":  post_straddle_b,
                }
                break
            next_date += pd.Timedelta(days=1)

        rows.append({
            "date":               str(row["date"])[:10],
            "er_date":            er_date_str,
            "closestraddle_a":    round(float(row["closestraddle_a"]), 4),
            "closestraddle_b":    round(float(row["closestraddle_b"]), 4),
            "closespystraddle_a": round(float(row["closespystraddle_a"]), 4),
            "closespystraddle_b": round(float(row["closespystraddle_b"]), 4),
            "stock_close":        stock_close,
            "post_stock_open":    post["stock_open"]      if post else None,
            "post_stock_close":   post["stock_close"]     if post else None,
            "open_chg_pct":       post["open_chg_pct"]   if post else None,
            "close_chg_pct":      post["close_chg_pct"]  if post else None,
            "post_closestraddle_a": post["closestraddle_a"] if post else None,
            "post_closestraddle_b": post["closestraddle_b"] if post else None,
        })

    response = {"ticker": sym, "dbe": 0, "data": rows}
    cache[cache_key] = {"data": response, "timestamp": datetime.now()}
    return response

@app.get("/scan")
def get_scan(dbe: int = 0):
    if df_global is None:
        raise HTTPException(status_code=503, detail="Parquet data not loaded.")

    cache_key = f"scan_{dbe}"
    if is_cache_valid(cache_key):
        return cache[cache_key]["data"]

    results = {}
    for ticker in sorted(df_global["ticker"].unique()):
        try:
            r = get_straddle_percentile(df_global, ticker=ticker, dbe=dbe)
            if r["hist_a"]["n"] < 3:
                continue
            results[ticker] = {
                "pct_a":            r["pct_a"],
                "pct_b":            r["pct_b"],
                "pct_ep":           r["pct_ep"],
                "signal_a":         r["signal_a"],
                "signal_b":         r["signal_b"],
                "signal_ep":        r["signal_ep"],
                "adj_signal_a":     r["adj_signal_a"],
                "adj_signal_b":     r["adj_signal_b"],
                "adj_signal_ep":    r["adj_signal_ep"],
                "composite":        r["composite"],
                "close_a":          r["close_a"],
                "close_b":          r["close_b"],
                "earnings_premium": r["earnings_premium"],
                "rel_a":            r["rel_a"],
                "rel_b":            r["rel_b"],
            }
        except Exception:
            continue

    response = {"data": results, "dbe": dbe, "count": len(results)}
    cache[cache_key] = {"data": response, "timestamp": datetime.now()}
    return response


@app.get("/analysis")
def get_analysis(dbe: int = 0):
    if df_global is None:
        raise HTTPException(status_code=503, detail="Parquet data not loaded.")

    cache_key = f"analysis_{dbe}"
    if is_cache_valid(cache_key):
        return cache[cache_key]["data"]

    results = []
    for ticker in sorted(df_global["ticker"].unique()):
        ticker_df = df_global[df_global["ticker"] == ticker]
        bucket = (
            ticker_df[ticker_df["dbe"] == dbe]
            .dropna(subset=["closestraddle_a"])
            .sort_values("date")
        )
        if len(bucket) < 3:
            continue

        vals = bucket["closestraddle_a"]

        results.append({
            "ticker":   ticker,
            "n":        int(len(vals)),
            "mean_a":   round(float(vals.mean()),         4),
            "std_a":    round(float(vals.std()),          4),
            "median_a": round(float(vals.median()),       4),
            "pct_25_a": round(float(vals.quantile(0.25)), 4),
            "pct_75_a": round(float(vals.quantile(0.75)), 4),
        })

    response = {"tickers": results, "dbe": dbe, "count": len(results)}
    cache[cache_key] = {"data": response, "timestamp": datetime.now()}
    return response


# Short-TTL cache for /watchlist-live -- this endpoint fans out to Alpaca, so
# a 6-hour cache (like the historical endpoints above) would defeat the
# point of it being "live," but no cache at all would mean every Watchlist
# screen open re-fires the same batch of calls. 60s keeps repeated opens/
# re-renders cheap while still refreshing about as often as the 5-minute
# paper-trading poll.
WATCHLIST_LIVE_CACHE = {}
WATCHLIST_LIVE_TTL_SECONDS = 60

# Alpaca throttles the whole account to 200 requests/minute, shared with the
# paper-trading cron -- not per-endpoint, not per-refresh. live_quotes.py
# batches its option-quote calls and reuses the stock price this endpoint
# already fetched (see live_quotes.py's module docstring point 4), which
# brings a near-term ticker's live lookup down to ~2 Alpaca calls (option
# chain + one batched quote call for all its legs). SPY is memoized across
# the whole batch on top of that (typically 1-2 real SPY fetches total, not
# one per ticker). Even at 130+ tickers that's ~260+ calls if EVERY ticker
# went live -- still over budget in one burst -- so live lookups stay
# scoped to tickers with near-term earnings (where "live" actually
# matters); everything else shows the historical percentile data the app
# already had before this feature. At ~2 calls/ticker, 60 near-term
# tickers is ~120 calls -- comfortable headroom under 200 for the SPY
# overhead, the price snapshot call, and anything the trading cron does in
# the same window. Raise MAX_LIVE_TICKERS if you want to push closer to
# the ceiling; the real constraint is calls/minute, not a hardcoded count.
WATCHLIST_LIVE_EARNINGS_WEEKS = 3
MAX_LIVE_TICKERS = 60


@app.get("/watchlist-live")
def get_watchlist_live():
    """Live price, daily % change for every ticker, plus a live (with
    historical fallback) percentile signal for tickers with near-term
    earnings -- powers the Watchlist screen's per-row display in place of
    the old dummyTicker() fabricated placeholder values. See the rate-limit
    comment above for why only near-term tickers get the live percentile
    calc; price/change is cheap (one batched call covers every ticker) so
    every row still gets a real live price regardless."""
    if df_global is None:
        raise HTTPException(status_code=503, detail="Parquet data not loaded.")

    cached = WATCHLIST_LIVE_CACHE.get("data")
    if cached and (datetime.now() - cached["timestamp"]) < timedelta(seconds=WATCHLIST_LIVE_TTL_SECONDS):
        return cached["data"]

    tickers = sorted(df_global["ticker"].unique().tolist())

    # Which tickers actually need a live option-chain lookup: those with a
    # CONFIRMED earnings date (see _confirmed_earnings_map) in the next
    # WATCHLIST_LIVE_EARNINGS_WEEKS weeks, soonest first, capped at
    # MAX_LIVE_TICKERS. A ticker with only an unconfirmed/estimated date
    # can't be anchored to an expiration (live_quotes.py point 5) and
    # wouldn't produce a trustworthy result anyway, so it's excluded here
    # rather than attempted and left to fail -- this also means fewer
    # doomed Alpaca calls than the old "any near-term date" scoping.
    live_tickers = dict(list(_confirmed_earnings_map(weeks=WATCHLIST_LIVE_EARNINGS_WEEKS).items())[:MAX_LIVE_TICKERS])

    # Batch price + previous close for every ticker in as few live calls as
    # possible (one Alpaca snapshot call per chunk of 200, not one call per
    # ticker) -- this alone stays cheap regardless of ticker count, so every
    # row gets a real live price even if it's outside the live_tickers set.
    price_data = {}
    try:
        from alpaca.data.historical.stock import StockHistoricalDataClient
        from alpaca.data.requests import StockSnapshotRequest
        stock_client = StockHistoricalDataClient(paper_trading.ALPACA_API_KEY, paper_trading.ALPACA_SECRET_KEY)
        CHUNK = 200
        for i in range(0, len(tickers), CHUNK):
            chunk = tickers[i:i + CHUNK]
            try:
                snaps = stock_client.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=chunk))
            except Exception as e:
                print(f"Watchlist snapshot batch failed for chunk starting {chunk[0]}: {e}")
                continue
            for sym, snap in snaps.items():
                try:
                    price = float(snap.latest_trade.price)
                    prev_close = float(snap.previous_daily_bar.close)
                    change_pct = ((price - prev_close) / prev_close * 100) if prev_close else None
                    price_data[sym] = {"price": price, "change_pct": change_pct}
                except Exception:
                    continue
    except Exception as e:
        print(f"Watchlist price snapshot fetch failed entirely: {e}")

    # Percentile signal + straddle value per ticker: live quote (only for
    # live_tickers) with a fallback to the historical calc, same pattern as
    # /straddle/{ticker}. spy_cache is shared across every ticker in this
    # batch -- most near-term tickers land on the same one or two nearest
    # Fridays, so this turns what would be dozens of duplicate SPY calls
    # into (at most) a couple of real ones. Run concurrently; even with the
    # earnings-window scoping, a live lookup is several sequential Alpaca
    # calls per ticker.
    spy_cache = {}

    def compute_one(ticker):
        # Per-ticker slice instead of the full 80k+-row df_global -- this
        # function runs once per ticker on every /watchlist-live call, so
        # skipping a full-table scan each time matters. TICKER_GROUPS now
        # holds row positions, not copied sub-DataFrames (see its
        # declaration above) -- .iloc[...] builds the small slice here, on
        # demand, instead of it having been copied and held in memory for
        # every ticker since startup.
        positions = TICKER_GROUPS.get(ticker)
        ticker_df = df_global.iloc[positions] if positions is not None else df_global

        if ticker in live_tickers:
            try:
                er_date, er_time = live_tickers[ticker]
                known_price = price_data.get(ticker, {}).get("price")
                live = live_quotes.get_live_straddle_inputs(
                    ticker, er_date, er_time, _spy_cache=spy_cache, stock_price=known_price
                )
                result = get_straddle_percentile_live(
                    ticker_df, ticker=ticker, dbe=0,
                    live_close_a=live["close_a"], live_close_b=live["close_b"],
                    live_spy_close_a=live["spy_close_a"], live_spy_close_b=live["spy_close_b"],
                )
                return result, True
            except Exception:
                pass  # falls through to the historical path below
        try:
            return get_straddle_percentile(ticker_df, ticker=ticker, dbe=0), False
        except Exception:
            return None, False

    now_iso = datetime.now().isoformat()
    results = {}
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(compute_one, t): t for t in tickers}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                result, is_live = future.result()
            except Exception as e:
                print(f"Watchlist live compute failed for {ticker}: {e}")
                result, is_live = None, False
            if result is None:
                continue

            pdata = price_data.get(ticker)
            price = pdata["price"] if pdata else None
            change_pct = pdata["change_pct"] if pdata else None
            straddle_pct = result.get("close_a")  # fraction of stock price, e.g. 0.037
            straddle_dollar = (straddle_pct * price) if (straddle_pct is not None and price is not None) else None

            results[ticker] = {
                "is_live":         is_live,
                "as_of":           now_iso,
                "price":           price,
                "change_pct":      change_pct,
                "straddle_pct":    straddle_pct,
                "straddle_dollar": straddle_dollar,
                "pct_a":           result.get("pct_a"),
                "pct_b":           result.get("pct_b"),
                "pct_ep":          result.get("pct_ep"),
                "signal_a":        result.get("signal_a"),
                "signal_b":        result.get("signal_b"),
                "signal_ep":       result.get("signal_ep"),
            }

    response = {"tickers": results, "count": len(results)}
    WATCHLIST_LIVE_CACHE["data"] = {"data": response, "timestamp": datetime.now()}
    return response


@app.get("/debug/{date_str}")
def debug_nasdaq(date_str: str):
    url = f"https://api.nasdaq.com/api/calendar/earnings?date={date_str}"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ── Push Notifications ────────────────────────────────────────────────────────
# The actual VAPID config, subscriber list, and send_push() now live in
# notifications.py, shared with paper_trading.py -- so a straddle alert and
# a paper trade (buy/sell) fire through the exact same code path instead of
# two copies of this that could quietly drift apart.
from notifications import VAPID_PUBLIC_KEY, load_subscriptions, save_subscriptions, send_push

ALERTS_CONFIG_FILE = Path(__file__).parent / "alerts_config.json"

WATCHLIST = ["NVDA", "ORCL", "ADBE", "TSLA", "AMZN", "META", "SPY"]


def load_alerts_config() -> dict:
    try:
        if ALERTS_CONFIG_FILE.exists():
            return json.loads(ALERTS_CONFIG_FILE.read_text())
    except Exception:
        pass
    return {"enabled": False, "threshold": 25}

def save_alerts_config(config: dict):
    ALERTS_CONFIG_FILE.write_text(json.dumps(config))


class PushSubscription(BaseModel):
    endpoint: str
    keys: dict

class AlertsConfig(BaseModel):
    enabled: bool
    threshold: int

class TradeNotifyConfig(BaseModel):
    enabled: bool


@app.post("/push/subscribe")
def subscribe(sub: PushSubscription):
    subs = load_subscriptions()
    # Avoid duplicate endpoints
    subs = [s for s in subs if s.get("endpoint") != sub.endpoint]
    subs.append({"endpoint": sub.endpoint, "keys": sub.keys})
    save_subscriptions(subs)
    return {"status": "subscribed"}

@app.post("/push/unsubscribe")
def unsubscribe(sub: PushSubscription):
    subs = load_subscriptions()
    subs = [s for s in subs if s.get("endpoint") != sub.endpoint]
    save_subscriptions(subs)
    return {"status": "unsubscribed"}

@app.post("/alerts/config")
def set_alerts_config(config: AlertsConfig):
    save_alerts_config({"enabled": config.enabled, "threshold": config.threshold})
    return {"status": "saved"}

@app.get("/alerts/config")
def get_alerts_config():
    return load_alerts_config()


@app.post("/push/test")
def test_push():
    """Send a test push notification to all subscribers."""
    subs = load_subscriptions()
    if not subs:
        return {"status": "no subscribers"}
    for sub in subs:
        send_push(sub, title="Insignia Test", body="Push notifications are working ✓")
    return {"status": "sent", "count": len(subs)}


@app.post("/alerts/trigger")
def trigger_alerts():
    """Check watchlist straddle percentiles against threshold and push alerts."""
    if df_global is None:
        return {"status": "no data"}

    config = load_alerts_config()
    if not config.get("enabled"):
        return {"status": "alerts disabled"}

    threshold = config.get("threshold", 25)
    subs = load_subscriptions()
    if not subs:
        return {"status": "no subscribers"}

    triggered = []
    confirmed_map = _confirmed_earnings_map()
    for sym in WATCHLIST:
        try:
            live = None
            confirmed = confirmed_map.get(sym)
            if confirmed:
                er_date, er_time = confirmed
                try:
                    live = live_quotes.get_live_straddle_inputs(sym, er_date, er_time)
                except Exception as e:
                    print(f"Live quote fetch failed for {sym}: {e}")

            if live:
                result = get_straddle_percentile_live(
                    df_global, ticker=sym, dbe=0,
                    live_close_a=live["close_a"], live_close_b=live["close_b"],
                    live_spy_close_a=live["spy_close_a"], live_spy_close_b=live["spy_close_b"],
                )
            else:
                result = get_straddle_percentile(df_global, ticker=sym, dbe=0)

            pct_a = result.get("pct_a", 100)
            if pct_a <= threshold:
                triggered.append({"ticker": sym, "pct_a": pct_a})
                for sub in subs:
                    send_push(
                        sub,
                        title=f"Insignia Alert — {sym}",
                        body=f"Straddle A at {pct_a}th percentile (below your {threshold}th threshold)"
                    )
        except Exception as e:
            print(f"Alert check error for {sym}: {e}")

    return {"status": "done", "triggered": triggered, "threshold": threshold}

# ---------------------------------------------------------------------------
# Paper trading — results tab + daily signal/execution cron target
# ---------------------------------------------------------------------------

@app.get("/paper-trading/summary")
def paper_trading_summary():
    try:
        return paper_trading.get_performance_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/paper-trading/account")
def paper_trading_account():
    """Current Alpaca paper-account value (equity/cash/day change) --
    powers the account-value figure at the top of the Paper Trading
    screen. See paper_trading.get_account_snapshot."""
    try:
        return paper_trading.get_account_snapshot()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/paper-trading/performance")
def paper_trading_performance(range: str = "1M"):
    """Account equity curve for the Paper Trading screen's performance
    chart. `range` is one of 1D/1W/1M/ALL. See
    paper_trading.get_performance_history."""
    try:
        return paper_trading.get_performance_history(range)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/paper-trading/trades")
def paper_trading_trades():
    try:
        return {"trades": paper_trading.get_all_trades()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/paper-trading/positions")
def paper_trading_positions():
    try:
        return {"positions": paper_trading.get_open_positions()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/paper-trading/positions-live")
def paper_trading_positions_live():
    """Open positions enriched with a live mark -- current estimated
    value, unrealized P&L vs. entry, this position's own day-over-day
    change (via Alpaca's historical option bars, not its snapshot -- see
    paper_trading.enrich_positions_live / _previous_option_closes), and
    the underlying's daily % change as secondary context -- powers the
    Paper Trading screen."""
    try:
        positions = paper_trading.get_open_positions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    try:
        positions = paper_trading.enrich_positions_live(positions)
    except Exception as e:
        print(f"Live position enrichment failed, returning static fields only: {e}")
    return {"positions": positions}


@app.get("/paper-trading/signals")
def paper_trading_signals(limit: int = 200):
    try:
        return {"signals": paper_trading.get_recent_signals(limit=limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/paper-trading/notifications-config")
def get_paper_trading_notify_config():
    return paper_trading.load_notify_config()


@app.post("/paper-trading/notifications-config")
def set_paper_trading_notify_config(config: TradeNotifyConfig):
    paper_trading.save_notify_config({"enabled": config.enabled})
    return {"status": "saved"}


@app.post("/paper-trading/run-daily-check")
def paper_trading_run_daily_check():
    """Called once a day by the insignia-paper-trading cron entry in
    render.yaml (same pattern as /alerts/trigger). Reuses the same NASDAQ
    earnings calendar the Earnings tab already shows, so there's a single
    source of truth for "what's coming up" across the whole app.
    """
    try:
        earnings_resp = get_earnings(universe="all", weeks=3)
        upcoming = {}
        for items in earnings_resp["grouped"].values():
            for item in items:
                upcoming[item["ticker"]] = {"date": item["date"], "time": item.get("time", "TBD")}
        results = paper_trading.run_daily_check(upcoming)
        return {"status": "done", **results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
