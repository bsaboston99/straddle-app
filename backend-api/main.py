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
from straddle_analysis import load_all_data, add_relative_straddles, get_straddle_percentile, get_straddle_percentile_live

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

MOCK_LIVE = {
    "NVDA": {"close_a": 0.0522, "close_b": 0.0669, "spy_close_a": 0.0078, "spy_close_b": 0.0151},
    "ORCL": {"close_a": 0.0666, "close_b": 0.0829, "spy_close_a": 0.0078, "spy_close_b": 0.0151},
    "ADBE": {"close_a": 0.0561, "close_b": 0.0698, "spy_close_a": 0.0078, "spy_close_b": 0.0151},
    "TSLA": {"close_a": 0.1028, "close_b": 0.1289, "spy_close_a": 0.0078, "spy_close_b": 0.0151},
    "AMZN": {"close_a": 0.0675, "close_b": 0.0852, "spy_close_a": 0.0078, "spy_close_b": 0.0151},
    "META": {"close_a": 0.0592, "close_b": 0.0738, "spy_close_a": 0.0078, "spy_close_b": 0.0151},
    "SPY":  {"close_a": 0.0208, "close_b": 0.0271, "spy_close_a": 0.0208, "spy_close_b": 0.0271},
}

df_global = None

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
    global df_global
    try:
        df_global = _load_df()
    except Exception as e:
        print(f"WARNING: Could not load data: {e}")
        df_global = None

    # Pre-warm earnings cache in background so first user doesn't wait
    asyncio.create_task(_prewarm_earnings())

async def _prewarm_earnings():
    await asyncio.sleep(3)  # let server finish starting
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: get_earnings(universe="all", weeks=8))
    print("Earnings pre-warm complete.")

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

@app.get("/straddle/{ticker}")
def get_straddle(ticker: str, dbe: int = 0):
    if df_global is None:
        raise HTTPException(status_code=503, detail="Parquet data not loaded.")

    cache_key = f"straddle_{ticker.upper()}_{dbe}"
    if is_cache_valid(cache_key):
        return cache[cache_key]["data"]

    sym = ticker.upper()

    try:
        if sym in MOCK_LIVE:
            live = MOCK_LIVE[sym]
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

VAPID_PUBLIC_KEY  = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_CLAIMS      = {"sub": "mailto:bsandersonn99@gmail.com"}

SUBSCRIPTIONS_FILE = Path(__file__).parent / "push_subscriptions.json"
ALERTS_CONFIG_FILE = Path(__file__).parent / "alerts_config.json"

WATCHLIST = ["NVDA", "ORCL", "ADBE", "TSLA", "AMZN", "META", "SPY"]


def load_subscriptions() -> list:
    try:
        if SUBSCRIPTIONS_FILE.exists():
            return json.loads(SUBSCRIPTIONS_FILE.read_text())
    except Exception:
        pass
    return []

def save_subscriptions(subs: list):
    SUBSCRIPTIONS_FILE.write_text(json.dumps(subs))

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


def send_push(subscription: dict, title: str, body: str):
    """Send a single Web Push notification."""
    try:
        from pywebpush import webpush, WebPushException
        webpush(
            subscription_info=subscription,
            data=json.dumps({"title": title, "body": body}),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS,
        )
    except Exception as e:
        print(f"Push send error: {e}")


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
    for sym in WATCHLIST:
        try:
            live = MOCK_LIVE.get(sym)
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